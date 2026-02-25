"""
Tool Proxy: единая точка контроля всех tool calls.

Обеспечивает:
- Валидацию аргументов (pydantic schemas)
- Allowlist/denylist проверки
- Rate limiting и loop detection
- Audit logging с TOOL_CALL_ID
- Timeout контроль
"""
import asyncio
import hashlib
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Dict, Optional
import structlog
from pydantic import ValidationError

from app.config import settings
from app.observability import metrics
from app.tool_proxy.registry import ToolRegistry
from app.tool_proxy.policies import ToolPolicy

logger = structlog.get_logger()


class ToolCallRecord:
    """Record of a single tool call for audit."""

    def __init__(
        self,
        tool_call_id: str,
        tool_name: str,
        args: Dict[str, Any],
        session_id: str,
        trace_id: str
    ):
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name
        self.args = args
        self.session_id = session_id
        self.trace_id = trace_id
        self.timestamp = time.time()
        self.result_hash: Optional[str] = None
        self.status: str = 'pending'
        self.error: Optional[str] = None
        self.duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for logging/storage."""
        return {
            'tool_call_id': self.tool_call_id,
            'tool_name': self.tool_name,
            'args': self.args,
            'session_id': self.session_id,
            'trace_id': self.trace_id,
            'timestamp': self.timestamp,
            'result_hash': self.result_hash,
            'status': self.status,
            'error': self.error,
            'duration': self.duration
        }


class ToolProxy:
    """
    Tool Proxy: контроль всех tool calls агента.

    Best practices (2026):
    - Credential injection через proxy (не даём агенту прямой доступ к секретам)
    - Validation всех аргументов перед выполнением
    - Loop detection (одинаковый вызов N раз → stop)
    - Rate limiting per session
    - Audit trail для каждого вызова
    """

    def __init__(self, registry: ToolRegistry, policy: ToolPolicy):
        self.registry = registry
        self.policy = policy

        # Rate limiting: session_id -> deque of timestamps
        self.call_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=settings.tool_rate_limit_per_min)
        )

        # Loop detection: (session_id, tool_name, args_hash) -> count
        self.loop_tracker: Dict[tuple, int] = defaultdict(int)

        # Audit records (в продакшене писать в Postgres)
        self.audit_records: list[ToolCallRecord] = []

    async def call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        session_id: str,
        trace_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Единая точка вызова любого tool.

        Returns:
            {
                'tool_call_id': str,
                'result': Any,
                'status': 'success' | 'error',
                'error': Optional[str]
            }
        """
        tool_call_id = str(uuid.uuid4())
        start_time = time.time()

        record = ToolCallRecord(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            args=args,
            session_id=session_id,
            trace_id=trace_id
        )

        logger.info(
            "Tool call initiated",
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            session_id=session_id,
            trace_id=trace_id
        )

        try:
            # 1. Policy check (allowlist/denylist)
            if not await self._check_policy(tool_name, context):
                raise PermissionError(f"Tool '{tool_name}' not allowed by policy")

            # 2. Rate limiting
            if not await self._check_rate_limit(session_id):
                raise RuntimeError(f"Rate limit exceeded for session {session_id}")

            # 3. Max calls per request
            session_calls = sum(
                1 for r in self.audit_records
                if r.session_id == session_id and r.trace_id == trace_id
            )

            if session_calls >= settings.tool_max_calls_per_request:
                raise RuntimeError(
                    f"Max calls per request exceeded ({settings.tool_max_calls_per_request})"
                )

            # 4. Loop detection
            args_hash = self._hash_args(args)
            loop_key = (session_id, tool_name, args_hash)
            self.loop_tracker[loop_key] += 1

            if self.loop_tracker[loop_key] > settings.tool_loop_breaker_threshold:
                raise RuntimeError(
                    f"Loop detected: same call repeated {self.loop_tracker[loop_key]} times"
                )

            # 5. Get tool from registry
            tool_def = self.registry.get_tool(tool_name)
            if not tool_def:
                raise ValueError(f"Unknown tool: {tool_name}")

            # 6. Validate arguments
            validated_args = tool_def.schema(**args)

            # 7. Execute with timeout
            result = await asyncio.wait_for(
                tool_def.execute(validated_args.model_dump()),
                timeout=settings.tool_timeout_seconds
            )

            # 8. Success
            record.status = 'success'
            record.result_hash = self._hash_result(result)
            record.duration = time.time() - start_time

            metrics.tool_calls_total.labels(
                tool_name=tool_name,
                status='success'
            ).inc()

            metrics.tool_call_duration.labels(tool_name=tool_name).observe(
                record.duration
            )

            logger.info(
                "Tool call succeeded",
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                duration=record.duration
            )

            return {
                'tool_call_id': tool_call_id,
                'result': result,
                'status': 'success',
                'error': None
            }

        except ValidationError as e:
            return await self._handle_error(record, e, 'validation_error', tool_name)

        except asyncio.TimeoutError as e:
            return await self._handle_error(record, e, 'timeout', tool_name)

        except PermissionError as e:
            return await self._handle_error(record, e, 'permission_denied', tool_name)

        except Exception as e:
            return await self._handle_error(record, e, 'execution_error', tool_name)

        finally:
            self.audit_records.append(record)

            # В продакшене: await self._persist_audit_record(record)

    async def _check_policy(
        self,
        tool_name: str,
        context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if tool is allowed by policy."""
        return await self.policy.is_allowed(tool_name, context)

    async def _check_rate_limit(self, session_id: str) -> bool:
        """Check rate limit for session."""
        now = time.time()
        window_start = now - 60  # 1 minute window

        # Remove old timestamps
        history = self.call_history[session_id]
        while history and history[0] < window_start:
            history.popleft()

        # Check limit
        if len(history) >= settings.tool_rate_limit_per_min:
            return False

        # Add current timestamp
        history.append(now)
        return True

    def _hash_args(self, args: Dict[str, Any]) -> str:
        """Hash arguments for loop detection."""
        import json
        serialized = json.dumps(args, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def _hash_result(self, result: Any) -> str:
        """Hash result for audit trail."""
        import json
        try:
            serialized = json.dumps(result, sort_keys=True)
            return hashlib.sha256(serialized.encode()).hexdigest()[:16]
        except:
            return "unhashable"

    async def _handle_error(
        self,
        record: ToolCallRecord,
        error: Exception,
        error_type: str,
        tool_name: str
    ) -> Dict[str, Any]:
        """Handle tool call error."""
        record.status = 'error'
        record.error = str(error)
        record.duration = time.time() - record.timestamp

        metrics.tool_calls_total.labels(
            tool_name=tool_name,
            status='error'
        ).inc()

        metrics.tool_call_errors_total.labels(
            tool_name=tool_name,
            error_type=error_type
        ).inc()

        logger.error(
            "Tool call failed",
            tool_call_id=record.tool_call_id,
            tool_name=tool_name,
            error_type=error_type,
            error=str(error)
        )

        return {
            'tool_call_id': record.tool_call_id,
            'result': None,
            'status': 'error',
            'error': f"{error_type}: {str(error)}"
        }

    def get_audit_trail(self, session_id: str, trace_id: str) -> list[Dict[str, Any]]:
        """Get audit trail for a request."""
        return [
            r.to_dict() for r in self.audit_records
            if r.session_id == session_id and r.trace_id == trace_id
        ]

    def get_tool_call_ids(self, session_id: str, trace_id: str) -> list[str]:
        """Get all TOOL_CALL_IDs for a request (for output rails verification)."""
        return [
            r.tool_call_id for r in self.audit_records
            if r.session_id == session_id
            and r.trace_id == trace_id
            and r.status == 'success'
        ]
