"""
LLM Topic Classifier.

Uses a small model to classify conversation topics and suggest guardrail rules.
"""
import json
import structlog
from typing import Any, Dict, List, Optional

from app.config import settings
from app.agent.llm_factory import create_chat_model

logger = structlog.get_logger()

CLASSIFICATION_PROMPT = """Ты — классификатор тем и рисков для системы guardrails. Проанализируй сообщение пользователя и определи:
1. Домены (темы) разговора
2. Потенциальные риски
3. Рекомендуемые правила безопасности

Существующие правила сессии (не дублируй их):
{existing_rules}

История разговора (последние сообщения):
{history}

Текущее сообщение пользователя:
{user_message}

Ответь СТРОГО в JSON формате:
{{
  "domains": ["medical", "financial", "legal", "technical", "personal_data", "general"],
  "risks": [
    {{"risk": "описание риска", "severity": "low|medium|high|critical"}}
  ],
  "suggested_rules": [
    {{
      "rule_id": "уникальный_id",
      "domain": "домен",
      "rule_type": "block|warn|require_disclaimer|restrict_tool",
      "description": "что делает правило",
      "severity": "low|medium|high|critical",
      "condition": "когда применять",
      "action": "что делать"
    }}
  ],
  "reasoning": "почему предложены эти правила (1-2 предложения)"
}}

Если сообщение не требует специальных правил, верни пустые списки risks и suggested_rules.
Не предлагай правила, которые уже существуют."""


class LLMTopicClassifier:
    """Classifies conversation topics and suggests guardrail rules using LLM."""

    def __init__(self):
        self.llm = None

    async def initialize(self):
        """Initialize the classifier LLM."""
        api_key = settings.llm_api_key or settings.openai_api_key
        model = settings.classifier_model or 'gpt-4o-mini'

        self.llm = create_chat_model(
            provider=settings.llm_provider,
            model=model,
            api_key=api_key,
            base_url=settings.llm_base_url,
            temperature=0.0,
        )
        logger.info("LLM topic classifier initialized", model=model)

    async def classify(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        existing_rules: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Classify the conversation and suggest rules.

        Args:
            user_message: Current user message
            history: Conversation history [{role, content}, ...]
            existing_rules: Already active rules (to avoid duplicates)

        Returns:
            Classification result with domains, risks, and suggested rules
        """
        if not self.llm:
            return {'domains': [], 'risks': [], 'suggested_rules': [], 'reasoning': ''}

        try:
            # Format existing rules
            existing_text = "Нет существующих правил."
            if existing_rules:
                lines = []
                for r in existing_rules:
                    rid = r.get('rule_id', r.get('id', '?'))
                    desc = r.get('description', '')
                    lines.append(f"- [{rid}] {desc}")
                existing_text = '\n'.join(lines)

            # Format history (last 5 messages)
            history_text = "Нет истории."
            if history:
                recent = history[-5:]
                lines = [f"{m['role']}: {m['content'][:200]}" for m in recent]
                history_text = '\n'.join(lines)

            prompt = CLASSIFICATION_PROMPT.format(
                existing_rules=existing_text,
                history=history_text,
                user_message=user_message,
            )

            from langchain_core.messages import HumanMessage
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # Parse JSON
            if content.startswith('```'):
                content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()

            result = json.loads(content)

            logger.info(
                "Classification complete",
                domains=result.get('domains', []),
                new_rules=len(result.get('suggested_rules', [])),
            )

            return result

        except json.JSONDecodeError as e:
            logger.warning("Classifier returned non-JSON", error=str(e))
            return {'domains': [], 'risks': [], 'suggested_rules': [], 'reasoning': ''}
        except Exception as e:
            logger.error("Classification failed", exc_info=e)
            return {'domains': [], 'risks': [], 'suggested_rules': [], 'reasoning': ''}
