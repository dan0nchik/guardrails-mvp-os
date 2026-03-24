"""
Guardrails Runtime — orchestrator.

Delegates guardrails checking to a pluggable backend (NeMo, LangChain, or none)
and agent execution to LangGraph runtime.

Flow:
1. backend.check_input() — if blocked, return refused
2. rule_engine.process_turn() — classify and generate dynamic rules (parallel with step 1)
3. backend.inject_rules() — apply dynamic rules
4. agent_runtime.run() — get agent response
5. backend.check_output() — if blocked, return refused
"""
import asyncio
import os
import time
import structlog
from typing import Any, Dict, List, Optional

from app.config import settings
from app.observability import metrics
from app.tool_proxy.proxy import ToolProxy
from app.tool_proxy.registry import ToolRegistry
from app.tool_proxy.policies import create_default_policy
from app.agent.langgraph_runtime import LangGraphAgentRuntime
from app.agent.tools import register_default_tools
from app.guardrails.factory import create_guardrails_backend
from app.guardrails.base import GuardrailsBackend

logger = structlog.get_logger()


class GuardrailsRuntime:
    """
    Guardrails orchestrator.

    Combines:
    - Pluggable guardrails backend (NeMo / LangChain / none)
    - LangGraph agent runtime (model-agnostic)
    - Dynamic rule engine (LLM-based classification)
    """

    def __init__(self):
        self.tool_registry = ToolRegistry()
        self.tool_policy = create_default_policy()
        self.tool_proxy = ToolProxy(self.tool_registry, self.tool_policy)
        self.agent_runtime: Optional[LangGraphAgentRuntime] = None
        self.backend: Optional[GuardrailsBackend] = None
        self.rule_engine = None  # Set in initialize() if dynamic rails enabled
        self.grounding_pipeline = None  # Set in initialize() if grounding enabled

    async def initialize(self):
        """Initialize guardrails runtime with all components."""
        logger.info("Initializing guardrails runtime",
                     backend=settings.guardrails_backend,
                     provider=settings.llm_provider)

        # Register default tools
        register_default_tools(self.tool_registry)

        # Initialize LangGraph agent runtime
        self.agent_runtime = LangGraphAgentRuntime(
            tool_proxy=self.tool_proxy,
            tool_registry=self.tool_registry,
        )
        await self.agent_runtime.initialize()

        # Initialize guardrails backend
        self.backend = create_guardrails_backend(settings.guardrails_backend)
        await self.backend.initialize()

        # Initialize dynamic rule engine if enabled
        if settings.dynamic_rails_enabled:
            try:
                from app.dynamic_rails.rule_engine import DynamicRuleEngine
                self.rule_engine = DynamicRuleEngine()
                await self.rule_engine.initialize()
                logger.info("Dynamic rule engine initialized")
            except Exception as e:
                logger.warning("Failed to initialize dynamic rule engine", error=str(e))
                self.rule_engine = None

        # Initialize grounding pipeline if enabled
        if settings.grounding_enabled:
            try:
                from app.grounding.pipeline import GroundingPipeline
                self.grounding_pipeline = GroundingPipeline()
                await self.grounding_pipeline.initialize()
                logger.info("Grounding pipeline initialized")
            except Exception as e:
                logger.warning("Failed to initialize grounding pipeline", error=str(e))
                self.grounding_pipeline = None

        logger.info("Guardrails runtime initialized successfully")

    async def switch_backend(self, backend_type: str):
        """Switch guardrails backend at runtime without restart."""
        logger.info("Switching guardrails backend", new_backend=backend_type)
        new_backend = create_guardrails_backend(backend_type)
        await new_backend.initialize()
        self.backend = new_backend
        settings.guardrails_backend = backend_type
        logger.info("Guardrails backend switched", backend=backend_type)

    async def switch_llm(self, provider: str, model: str):
        """Switch LLM provider/model at runtime without restart."""
        logger.info("Switching LLM", provider=provider, model=model)
        await self.agent_runtime.switch_llm(provider, model)
        settings.llm_provider = provider
        settings.llm_model = model
        logger.info("LLM switched", provider=provider, model=model)

    async def generate(
        self,
        user_message: str,
        session_state: Dict[str, Any],
        agent_profile: str,
        trace_id: str,
        history: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Generate response through guardrails pipeline.

        Returns:
            {
                'message': str,
                'status': 'ok' | 'refused' | 'escalated',
                'tool_calls': List[str],
                'session_state': Dict,
                'dynamic_rules_result': Optional[Dict]  # from rule engine
            }
        """
        start_time = time.time()
        session_id = session_state.get('session_id', trace_id)

        logger.info("Guardrails generate started", trace_id=trace_id, profile=agent_profile)

        try:
            context = {
                'session_id': session_id,
                'trace_id': trace_id,
                'profile': agent_profile,
                'history': history or [],
            }

            # Step 1+2: Parallel — check input + classify dynamic rules
            tasks = [self.backend.check_input(user_message, context)]

            if self.rule_engine:
                tasks.append(
                    self.rule_engine.process_turn(
                        user_message=user_message,
                        session_state=session_state,
                        history=history or [],
                    )
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process input check
            input_result = results[0]
            if isinstance(input_result, Exception):
                logger.error("Input check failed", exc_info=input_result)
                input_result = None

            if input_result and input_result.blocked:
                logger.warning("Input blocked by guardrails", trace_id=trace_id, reason=input_result.reason)
                metrics.refusals_total.inc()
                return {
                    'message': input_result.reason or "Сообщение заблокировано барьерами безопасности.",
                    'status': 'refused',
                    'tool_calls': [],
                    'session_state': session_state,
                    'dynamic_rules_result': None,
                    'grounding_result': None,
                }

            # Process dynamic rules
            dynamic_rules_result = None
            if self.rule_engine and len(results) > 1:
                rules_result = results[1]
                if isinstance(rules_result, Exception):
                    logger.warning("Dynamic rules classification failed", exc_info=rules_result)
                else:
                    dynamic_rules_result = rules_result
                    # Inject rules into backend
                    if rules_result and rules_result.get('all_active_rules'):
                        try:
                            from app.guardrails.base import DynamicRule
                            rules = [
                                DynamicRule(**r) if isinstance(r, dict) else r
                                for r in rules_result['all_active_rules']
                            ]
                            await self.backend.inject_rules(rules)
                        except Exception as e:
                            logger.warning("Failed to inject dynamic rules", error=str(e))

            # Step 3: Run agent
            result = await self.agent_runtime.run(
                user_message=user_message,
                session_id=session_id,
                trace_id=trace_id,
                context=session_state,
                history=history,
            )

            assistant_message = result['message']
            tool_calls = self.tool_proxy.get_tool_call_ids(session_id, trace_id)

            # Step 3.5: Grounding pipeline (if enabled)
            grounding_result = None
            if self.grounding_pipeline and settings.grounding_enabled:
                try:
                    grounding_result = await self.grounding_pipeline.ground(
                        draft_response=assistant_message,
                        trace_id=trace_id,
                    )
                    assistant_message = grounding_result.grounded_response
                    logger.info(
                        "Grounding completed",
                        trace_id=trace_id,
                        claims_total=grounding_result.claims_total,
                        claims_verified=grounding_result.claims_verified,
                        claims_unverified=grounding_result.claims_unverified,
                        duration_ms=round(grounding_result.pipeline_duration_ms, 1),
                    )
                except Exception as e:
                    logger.warning("Grounding pipeline failed, using original response", exc_info=e)

            # Step 4: Check output
            try:
                output_result = await self.backend.check_output(assistant_message, context)
                if output_result and output_result.blocked:
                    logger.warning("Output blocked by guardrails", trace_id=trace_id)
                    metrics.refusals_total.inc()
                    return {
                        'message': output_result.reason or "Ответ заблокирован барьерами безопасности.",
                        'status': 'refused',
                        'tool_calls': tool_calls,
                        'session_state': session_state,
                        'dynamic_rules_result': dynamic_rules_result,
                        'grounding_result': grounding_result,
                    }
            except Exception as e:
                logger.warning("Output check failed", exc_info=e)

            # Update session state with dynamic rules
            if dynamic_rules_result and dynamic_rules_result.get('all_active_rules'):
                session_state['dynamic_rules'] = dynamic_rules_result['all_active_rules']

            duration = time.time() - start_time
            metrics.agent_duration.labels(profile=agent_profile).observe(duration)

            logger.info("Guardrails generate completed", trace_id=trace_id, duration=duration)

            return {
                'message': assistant_message,
                'status': 'ok' if result['status'] == 'success' else 'escalated',
                'tool_calls': tool_calls,
                'session_state': session_state,
                'dynamic_rules_result': dynamic_rules_result,
                'grounding_result': grounding_result,
            }

        except Exception as e:
            logger.error("Guardrails generate failed", exc_info=e, trace_id=trace_id)
            return {
                'message': "Извините, произошла ошибка при обработке вашего запроса.",
                'status': 'escalated',
                'tool_calls': [],
                'session_state': session_state,
                'dynamic_rules_result': None,
                'grounding_result': None,
            }

    async def generate_passthrough(
        self,
        user_message: str,
        session_state: Dict[str, Any],
        agent_profile: str,
        trace_id: str,
        history: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Generate response WITHOUT guardrails — direct LLM call.
        Used when guardrails are globally disabled.
        """
        start_time = time.time()
        session_id = session_state.get('session_id', trace_id)

        logger.info("Passthrough generate (guardrails disabled)", trace_id=trace_id)

        try:
            result = await self.agent_runtime.run(
                user_message=user_message,
                session_id=session_id,
                trace_id=trace_id,
                context=session_state,
                history=history,
            )

            tool_calls = self.tool_proxy.get_tool_call_ids(session_id, trace_id)
            duration = time.time() - start_time

            logger.info("Passthrough generate completed", trace_id=trace_id, duration=duration)

            return {
                'message': result['message'],
                'status': 'ok' if result['status'] == 'success' else 'escalated',
                'tool_calls': tool_calls,
                'session_state': session_state,
                'dynamic_rules_result': None,
                'grounding_result': None,
            }

        except Exception as e:
            logger.error("Passthrough generate failed", exc_info=e, trace_id=trace_id)
            return {
                'message': "Извините, произошла ошибка при обработке вашего запроса.",
                'status': 'escalated',
                'tool_calls': [],
                'session_state': session_state,
                'dynamic_rules_result': None,
                'grounding_result': None,
            }
