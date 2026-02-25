"""
Guardrails backend factory.

Creates the appropriate backend based on configuration.
"""
import structlog
from app.guardrails.base import GuardrailsBackend, GuardrailsResult, DynamicRule
from typing import Any, Dict, List

logger = structlog.get_logger()


class NoopGuardrailsBackend(GuardrailsBackend):
    """Passthrough backend — no guardrails checking."""

    async def initialize(self) -> None:
        logger.info("Noop guardrails backend initialized (no guardrails)")

    async def check_input(self, user_message: str, context: Dict[str, Any]) -> GuardrailsResult:
        return GuardrailsResult()

    async def check_output(self, assistant_message: str, context: Dict[str, Any]) -> GuardrailsResult:
        return GuardrailsResult()

    async def inject_rules(self, rules: List[DynamicRule]) -> None:
        pass


def create_guardrails_backend(backend_type: str) -> GuardrailsBackend:
    """
    Create a guardrails backend by type.

    Args:
        backend_type: 'nemo', 'langchain', or 'none'

    Returns:
        GuardrailsBackend instance
    """
    if backend_type == 'nemo':
        from app.guardrails.nemo_backend import NemoGuardrailsBackend
        logger.info("Creating NeMo guardrails backend")
        return NemoGuardrailsBackend()

    elif backend_type == 'langchain':
        from app.guardrails.langchain_backend import LangChainGuardrailsBackend
        logger.info("Creating LangChain guardrails backend")
        return LangChainGuardrailsBackend()

    elif backend_type == 'none':
        logger.info("Creating noop guardrails backend")
        return NoopGuardrailsBackend()

    else:
        logger.warning(f"Unknown guardrails backend: {backend_type}, using noop")
        return NoopGuardrailsBackend()
