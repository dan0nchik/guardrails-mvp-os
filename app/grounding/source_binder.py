"""
Source Binder — finds evidence for claims from indexed source documents.

For each claim:
1. Query ChromaDB for top-K relevant chunks
2. Run LLM-based NLI verification on each (claim, chunk) pair
3. Return the best evidence result
"""
import asyncio
import json
import re
from typing import Dict, List, Optional

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.grounding.indexer import DocumentIndexer
from app.grounding.models import Claim, EvidenceResult

logger = structlog.get_logger()

NLI_VERIFICATION_PROMPT = """Ты — система проверки фактов. Определи, подтверждает ли приведённый отрывок из источника данное утверждение.

Утверждение (claim):
{claim_text}

Отрывок из источника:
{passage}

Источник: {source_file}, раздел: {section}

Оцени отношение между утверждением и отрывком:
- SUPPORTS: отрывок прямо подтверждает утверждение (факты совпадают)
- REFUTES: отрывок прямо противоречит утверждению (факты расходятся)
- NOT_ENOUGH_INFO: отрывок не содержит достаточной информации для проверки

Ответь СТРОГО в JSON формате:
{{
  "status": "SUPPORTS|REFUTES|NOT_ENOUGH_INFO",
  "confidence": 0.85,
  "reasoning": "краткое объяснение (1-2 предложения)"
}}"""


def _parse_nli_response(text: str) -> dict:
    """Parse NLI JSON response from LLM."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text)


class SourceBinder:
    """Binds claims to evidence from source documents."""

    def __init__(
        self,
        indexer: DocumentIndexer,
        llm: BaseChatModel,
        relevance_threshold: float = 0.3,
        nli_threshold: float = 0.7,
        top_k: int = 3,
    ):
        self.indexer = indexer
        self.llm = llm
        self.relevance_threshold = relevance_threshold
        self.nli_threshold = nli_threshold
        self.top_k = top_k

    async def bind(self, claim: Claim) -> Optional[EvidenceResult]:
        """
        Find evidence for a single claim.

        Returns EvidenceResult if evidence found, None otherwise.
        """
        # Search for relevant chunks
        search_results = await self.indexer.search(claim.text, k=self.top_k)

        # Filter by relevance threshold
        candidates = [r for r in search_results if r["relevance_score"] >= self.relevance_threshold]

        if not candidates:
            return None

        # Run NLI on each candidate
        for candidate in candidates:
            try:
                nli_result = await self._verify_nli(claim, candidate)
                if nli_result is None:
                    continue

                status = nli_result.get("status", "NOT_ENOUGH_INFO")
                confidence = float(nli_result.get("confidence", 0.0))

                if status in ("SUPPORTS", "REFUTES") and confidence >= self.nli_threshold:
                    return EvidenceResult(
                        claim_id=claim.id,
                        source_path=candidate["metadata"].get("source_file", ""),
                        section=candidate["metadata"].get("section", ""),
                        passage=candidate["text"][:500],  # Truncate long passages
                        relevance_score=candidate["relevance_score"],
                        nli_status=status,
                        nli_confidence=confidence,
                    )
            except Exception as e:
                logger.warning("NLI verification failed for candidate", error=str(e))
                continue

        return None

    async def _verify_nli(self, claim: Claim, candidate: dict) -> Optional[dict]:
        """Run NLI verification between a claim and a candidate passage."""
        prompt = NLI_VERIFICATION_PROMPT.format(
            claim_text=claim.text,
            passage=candidate["text"][:1000],  # Limit passage length for LLM
            source_file=candidate["metadata"].get("source_file", "unknown"),
            section=candidate["metadata"].get("section", "unknown"),
        )

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content if hasattr(response, "content") else str(response)
            return _parse_nli_response(content)
        except json.JSONDecodeError:
            return None
        except Exception as e:
            logger.warning("NLI LLM call failed", error=str(e))
            return None

    async def bind_all(self, claims: List[Claim]) -> Dict[str, Optional[EvidenceResult]]:
        """
        Find evidence for all claims in parallel.

        Returns dict mapping claim_id to EvidenceResult (or None).
        """
        tasks = [self.bind(claim) for claim in claims]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        evidence_map = {}
        for claim, result in zip(claims, results):
            if isinstance(result, Exception):
                logger.warning("Evidence binding failed for claim", claim_id=claim.id, error=str(result))
                evidence_map[claim.id] = None
            else:
                evidence_map[claim.id] = result

        found = sum(1 for v in evidence_map.values() if v is not None)
        logger.info("Evidence binding complete", total=len(claims), found=found)

        return evidence_map
