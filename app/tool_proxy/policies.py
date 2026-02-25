"""Tool policies: allowlist, denylist, per-environment rules."""
from typing import Dict, Any, Optional, Set
import structlog

logger = structlog.get_logger()


class ToolPolicy:
    """
    Tool access policy engine.

    Controls which tools are allowed based on:
    - Global allowlist/denylist
    - Agent profile
    - Environment
    - Context (optional: user role, domain, etc.)
    """

    def __init__(
        self,
        allowlist: Optional[Set[str]] = None,
        denylist: Optional[Set[str]] = None,
        default_allow: bool = True
    ):
        """
        Initialize policy.

        Args:
            allowlist: If set, only these tools are allowed
            denylist: These tools are always denied
            default_allow: If True, allow tools not in lists (default)
        """
        self.allowlist = allowlist or set()
        self.denylist = denylist or set()
        self.default_allow = default_allow

    async def is_allowed(
        self,
        tool_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if tool is allowed.

        Priority:
        1. Denylist (always block)
        2. Allowlist (if defined)
        3. Default policy
        """
        context = context or {}

        # 1. Check denylist (highest priority)
        if tool_name in self.denylist:
            logger.warning(
                "Tool denied by denylist",
                tool_name=tool_name,
                context=context
            )
            return False

        # 2. Check allowlist (if defined)
        if self.allowlist:
            allowed = tool_name in self.allowlist
            if not allowed:
                logger.warning(
                    "Tool not in allowlist",
                    tool_name=tool_name,
                    context=context
                )
            return allowed

        # 3. Default policy
        return self.default_allow

    def add_to_allowlist(self, tool_name: str):
        """Add tool to allowlist."""
        self.allowlist.add(tool_name)
        logger.info("Tool added to allowlist", tool_name=tool_name)

    def add_to_denylist(self, tool_name: str):
        """Add tool to denylist."""
        self.denylist.add(tool_name)
        logger.info("Tool added to denylist", tool_name=tool_name)

    def remove_from_allowlist(self, tool_name: str):
        """Remove tool from allowlist."""
        self.allowlist.discard(tool_name)
        logger.info("Tool removed from allowlist", tool_name=tool_name)

    def remove_from_denylist(self, tool_name: str):
        """Remove tool from denylist."""
        self.denylist.discard(tool_name)
        logger.info("Tool removed from denylist", tool_name=tool_name)


def create_default_policy() -> ToolPolicy:
    """
    Create default policy for MVP.

    Denylist опасных инструментов:
    - Команды системы (rm, shutdown, etc.) - если будут
    - Network tools без ограничений
    - Database write operations (в MVP читаем, но не пишем)
    """
    dangerous_tools = {
        'execute_system_command',  # пример
        'delete_database',
        'unrestricted_http_request'
    }

    policy = ToolPolicy(
        denylist=dangerous_tools,
        default_allow=True
    )

    logger.info(
        "Default policy created",
        denylist=list(dangerous_tools),
        default_allow=True
    )

    return policy
