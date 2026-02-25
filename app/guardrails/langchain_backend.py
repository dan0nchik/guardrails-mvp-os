"""
LangChain Guardrails backend — LLM-as-a-judge pattern.

Uses a small/fast model (e.g. gpt-4o-mini) to evaluate input/output
against a dynamic list of active rules. Rules can be injected at runtime.
"""
import json
import structlog
from typing import Any, Dict, List

from app.guardrails.base import GuardrailsBackend, GuardrailsResult, DynamicRule
from app.config import settings
from app.agent.llm_factory import create_chat_model

logger = structlog.get_logger()

INPUT_CHECK_PROMPT = """Ты — safety evaluator. Твоя задача — проверить пользовательское сообщение на соответствие правилам.

Активные правила:
{rules}

Сообщение пользователя:
{message}

Для каждого правила оцени: PASS (нет нарушений), WARN (возможное нарушение), BLOCK (явное нарушение).

Ответь СТРОГО в JSON формате:
{{
  "overall": "PASS" | "WARN" | "BLOCK",
  "reason": "краткое объяснение (1-2 предложения)",
  "checks": [
    {{"rule_id": "...", "verdict": "PASS|WARN|BLOCK", "reason": "..."}}
  ]
}}"""

OUTPUT_CHECK_PROMPT = """Ты — safety evaluator. Твоя задача — проверить ответ ассистента на соответствие правилам.

Активные правила:
{rules}

Ответ ассистента:
{message}

Для каждого правила оцени: PASS (нет нарушений), WARN (возможное нарушение), BLOCK (явное нарушение).

Ответь СТРОГО в JSON формате:
{{
  "overall": "PASS" | "WARN" | "BLOCK",
  "reason": "краткое объяснение (1-2 предложения)",
  "checks": [
    {{"rule_id": "...", "verdict": "PASS|WARN|BLOCK", "reason": "..."}}
  ]
}}"""


class LangChainGuardrailsBackend(GuardrailsBackend):
    """LLM-as-a-judge guardrails backend."""

    def __init__(self):
        self.judge_llm = None
        self.active_rules: List[DynamicRule] = []

    async def initialize(self) -> None:
        """Initialize the judge LLM (small, fast model)."""
        api_key = settings.llm_api_key or settings.openai_api_key
        judge_model = settings.classifier_model or 'gpt-4o-mini'

        try:
            self.judge_llm = create_chat_model(
                provider=settings.llm_provider,
                model=judge_model,
                api_key=api_key,
                base_url=settings.llm_base_url,
                temperature=0.0,
            )
            logger.info("LangChain guardrails backend initialized", model=judge_model)
        except Exception as e:
            logger.warning("Failed to initialize judge LLM", error=str(e))
            self.judge_llm = None

    async def check_input(self, user_message: str, context: Dict[str, Any]) -> GuardrailsResult:
        """Check user input with LLM-as-judge."""
        if not self.judge_llm or not self.active_rules:
            return GuardrailsResult()

        return await self._evaluate(user_message, INPUT_CHECK_PROMPT)

    async def check_output(self, assistant_message: str, context: Dict[str, Any]) -> GuardrailsResult:
        """Check assistant output with LLM-as-judge."""
        if not self.judge_llm or not self.active_rules:
            return GuardrailsResult()

        return await self._evaluate(assistant_message, OUTPUT_CHECK_PROMPT)

    async def inject_rules(self, rules: List[DynamicRule]) -> None:
        """Update the active rules list (fast — just updates prompt context)."""
        self.active_rules = rules
        logger.info("LangChain backend rules updated", count=len(rules))

    async def _evaluate(self, message: str, prompt_template: str) -> GuardrailsResult:
        """Run LLM-as-judge evaluation."""
        try:
            rules_text = self._format_rules()
            prompt = prompt_template.format(rules=rules_text, message=message)

            from langchain_core.messages import HumanMessage
            response = await self.judge_llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # Parse JSON response
            # Handle markdown code blocks
            if content.startswith('```'):
                content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()

            parsed = json.loads(content)
            overall = parsed.get('overall', 'PASS')
            reason = parsed.get('reason', '')

            if overall == 'BLOCK':
                return GuardrailsResult(
                    blocked=True,
                    reason=reason,
                    severity='block',
                    details={'checks': parsed.get('checks', [])},
                )
            elif overall == 'WARN':
                return GuardrailsResult(
                    blocked=False,
                    reason=reason,
                    severity='warn',
                    details={'checks': parsed.get('checks', [])},
                )
            else:
                return GuardrailsResult()

        except json.JSONDecodeError as e:
            logger.warning("Judge LLM returned non-JSON response", error=str(e))
            return GuardrailsResult()
        except Exception as e:
            logger.error("LLM-as-judge evaluation failed", exc_info=e)
            return GuardrailsResult()

    def _format_rules(self) -> str:
        """Format active rules for the judge prompt."""
        if not self.active_rules:
            return "Нет активных правил."

        lines = []
        for rule in self.active_rules:
            lines.append(
                f"- [{rule.rule_id}] ({rule.severity}) {rule.rule_type}: {rule.description}"
            )
        return '\n'.join(lines)
