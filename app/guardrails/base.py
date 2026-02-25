"""
Abstract guardrails backend interface and shared data classes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DynamicRule:
    """A single dynamic guardrail rule."""
    rule_id: str = ''
    domain: str = ''
    rule_type: str = 'block'  # block | warn | require_disclaimer | restrict_tool
    description: str = ''
    severity: str = 'medium'  # low | medium | high | critical
    condition: str = ''  # When to apply
    action: str = ''  # What to do


@dataclass
class GuardrailsResult:
    """Result of a guardrails check (input or output)."""
    blocked: bool = False
    reason: Optional[str] = None
    severity: str = 'info'  # info | warn | block
    rule_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class GuardrailsBackend(ABC):
    """
    Abstract interface for guardrails backends.

    Implementations: NeMo, LangChain (LLM-as-judge), None (passthrough).
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the backend (load models, configs, etc.)."""
        ...

    @abstractmethod
    async def check_input(self, user_message: str, context: Dict[str, Any]) -> GuardrailsResult:
        """
        Check user input against active rules.

        Args:
            user_message: The user's message
            context: Session/request context

        Returns:
            GuardrailsResult with blocked=True if message should be blocked
        """
        ...

    @abstractmethod
    async def check_output(self, assistant_message: str, context: Dict[str, Any]) -> GuardrailsResult:
        """
        Check assistant output against active rules.

        Args:
            assistant_message: The assistant's response
            context: Session/request context

        Returns:
            GuardrailsResult with blocked=True if response should be blocked
        """
        ...

    @abstractmethod
    async def inject_rules(self, rules: List[DynamicRule]) -> None:
        """
        Inject dynamic rules into the backend.

        Called by the dynamic rule engine to add new rules mid-session.

        Args:
            rules: List of DynamicRule objects to apply
        """
        ...
