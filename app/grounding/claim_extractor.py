"""
Claim Extractor — extracts atomic verifiable claims from LLM responses.

Uses an LLM call with a structured prompt to decompose a response into
individual claims with type classification and confidence scores.
"""
import json
import re
from typing import List

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.grounding.models import Claim, ClaimType

logger = structlog.get_logger()

CLAIM_EXTRACTION_PROMPT = """Ты — система извлечения утверждений из текста. Твоя задача — разбить текст на атомарные утверждения (claims).

Текст для анализа:
{text}

Правила:
1. Каждое утверждение должно быть АТОМАРНЫМ — одна проверяемая мысль.
2. Пропускай тривиальные фразы: приветствия, «Я могу помочь», «Вот информация», вводные слова.
3. Для каждого утверждения определи тип:
   - factual: утверждение о факте (определение, свойство, характеристика)
   - statistical: числовые данные, статистика, проценты
   - recommendation: рекомендация по лечению, дозировке, процедуре
   - temporal: утверждение с временным контекстом (даты, сроки, периоды)
   - causal: причинно-следственная связь
4. Оцени уверенность (confidence) от 0 до 1: насколько конкретно и проверяемо утверждение.
5. Укажи исходное предложение, из которого извлечено утверждение.

Ответь СТРОГО в JSON формате:
{{
  "claims": [
    {{
      "text": "атомарное утверждение",
      "type": "factual|statistical|recommendation|temporal|causal",
      "confidence": 0.9,
      "original_sentence": "исходное предложение из текста"
    }}
  ]
}}"""

# Patterns for trivial claims to filter out
_TRIVIAL_PATTERNS = [
    re.compile(r"^(я|мы)\s+(могу|можем|помогу|готов)", re.IGNORECASE),
    re.compile(r"^вот\s+", re.IGNORECASE),
    re.compile(r"^давайте\s+", re.IGNORECASE),
    re.compile(r"^конечно", re.IGNORECASE),
    re.compile(r"^с удовольствием", re.IGNORECASE),
    re.compile(r"^обратите внимание", re.IGNORECASE),
    re.compile(r"^пожалуйста", re.IGNORECASE),
    re.compile(r"^рад помочь", re.IGNORECASE),
]


def _is_trivial(text: str) -> bool:
    """Check if a claim text is trivial and should be filtered."""
    return any(p.match(text.strip()) for p in _TRIVIAL_PATTERNS)


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    # Strip markdown code blocks if present
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text)


class ClaimExtractor:
    """Extracts atomic claims from LLM-generated text."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    async def extract(self, text: str) -> List[Claim]:
        """
        Extract atomic claims from text via LLM call.

        Args:
            text: The LLM response text to extract claims from.

        Returns:
            List of Claim objects.
        """
        if not text or len(text.strip()) < 20:
            return []

        prompt = CLAIM_EXTRACTION_PROMPT.format(text=text)

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content if hasattr(response, "content") else str(response)

            parsed = _parse_json_response(content)
            raw_claims = parsed.get("claims", [])

            claims = []
            for raw in raw_claims:
                claim_text = raw.get("text", "").strip()
                if not claim_text or _is_trivial(claim_text):
                    continue

                claim_type_str = raw.get("type", "factual")
                try:
                    claim_type = ClaimType(claim_type_str)
                except ValueError:
                    claim_type = ClaimType.FACTUAL

                claims.append(Claim(
                    text=claim_text,
                    type=claim_type,
                    confidence=float(raw.get("confidence", 0.5)),
                    original_sentence=raw.get("original_sentence", ""),
                ))

            logger.info("Claims extracted", count=len(claims), original_length=len(text))
            return claims

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse claim extraction JSON", error=str(e))
            return []
        except Exception as e:
            logger.warning("Claim extraction failed", error=str(e))
            return []
