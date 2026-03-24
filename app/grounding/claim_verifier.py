"""
Claim Verifier — assigns final verdicts to claims based on evidence.

Pure deterministic logic, no LLM calls.
"""
from typing import Dict, List, Optional

import structlog

from app.grounding.models import Claim, EvidenceResult, Verdict, VerdictStatus

logger = structlog.get_logger()

SKIP_CONFIDENCE_THRESHOLD = 0.3


class ClaimVerifier:
    """Assigns verdicts to claims based on evidence binding results."""

    def verify(self, claim: Claim, evidence: Optional[EvidenceResult]) -> Verdict:
        """
        Assign a verdict to a single claim.

        Logic:
        - claim.confidence < 0.3 → SKIP (trivial/vague claim)
        - evidence is None → UNVERIFIED
        - evidence.nli_status == SUPPORTS → VERIFIED
        - evidence.nli_status == REFUTES → REFUTED
        - otherwise → UNVERIFIED
        """
        if claim.confidence < SKIP_CONFIDENCE_THRESHOLD:
            return Verdict(
                claim_id=claim.id,
                claim_text=claim.text,
                status=VerdictStatus.SKIP,
                confidence=claim.confidence,
                reason="Утверждение слишком общее или неконкретное для верификации",
            )

        if evidence is None:
            return Verdict(
                claim_id=claim.id,
                claim_text=claim.text,
                status=VerdictStatus.UNVERIFIED,
                confidence=0.0,
                reason="Не найдено подтверждающих источников в базе клинических рекомендаций",
            )

        if evidence.nli_status == "SUPPORTS":
            return Verdict(
                claim_id=claim.id,
                claim_text=claim.text,
                status=VerdictStatus.VERIFIED,
                evidence=evidence,
                confidence=evidence.nli_confidence,
                reason=f"Подтверждено источником: {evidence.source_path}, раздел: {evidence.section}",
            )

        if evidence.nli_status == "REFUTES":
            return Verdict(
                claim_id=claim.id,
                claim_text=claim.text,
                status=VerdictStatus.REFUTED,
                evidence=evidence,
                confidence=evidence.nli_confidence,
                reason=f"Опровергнуто источником: {evidence.source_path}, раздел: {evidence.section}",
            )

        # NOT_ENOUGH_INFO or unknown
        return Verdict(
            claim_id=claim.id,
            claim_text=claim.text,
            status=VerdictStatus.UNVERIFIED,
            evidence=evidence,
            confidence=evidence.nli_confidence,
            reason="Источник найден, но недостаточно информации для подтверждения",
        )

    def verify_all(
        self,
        claims: List[Claim],
        evidence_map: Dict[str, Optional[EvidenceResult]],
    ) -> List[Verdict]:
        """Verify all claims and return list of verdicts."""
        verdicts = [self.verify(claim, evidence_map.get(claim.id)) for claim in claims]

        counts = {}
        for v in verdicts:
            counts[v.status.value] = counts.get(v.status.value, 0) + 1

        logger.info("Verdicts assigned", **counts, total=len(verdicts))
        return verdicts
