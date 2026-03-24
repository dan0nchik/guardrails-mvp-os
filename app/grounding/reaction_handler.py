"""
Reaction Handler — applies grounding verdicts to produce the final response.

Modes:
- enforce: remove REFUTED/UNVERIFIED sentences, add source references for VERIFIED
- monitor: don't modify response, only log verdicts
- strict: block entire response if any claim is REFUTED or UNVERIFIED
"""
import re
from typing import List, Set

import structlog

from app.grounding.models import GroundingMode, GroundingResult, Verdict, VerdictStatus

logger = structlog.get_logger()


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences, preserving structure."""
    # Split on sentence-ending punctuation followed by space or newline
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def _sentence_contains_claim(sentence: str, original_sentence: str) -> bool:
    """Check if a sentence matches or contains the claim's original sentence."""
    if not original_sentence:
        return False
    # Normalize whitespace for comparison
    norm_sent = " ".join(sentence.lower().split())
    norm_orig = " ".join(original_sentence.lower().split())
    # Check substring match (original_sentence may be a subset)
    return norm_orig in norm_sent or norm_sent in norm_orig


class ReactionHandler:
    """Applies reactions based on claim verdicts."""

    def __init__(self, mode: GroundingMode):
        self.mode = mode

    def apply(self, original_response: str, verdicts: List[Verdict]) -> GroundingResult:
        """
        Apply verdict-based reactions to produce the grounded response.

        Returns GroundingResult with the (potentially modified) response.
        """
        counts = {
            "verified": sum(1 for v in verdicts if v.status == VerdictStatus.VERIFIED),
            "refuted": sum(1 for v in verdicts if v.status == VerdictStatus.REFUTED),
            "unverified": sum(1 for v in verdicts if v.status == VerdictStatus.UNVERIFIED),
            "skipped": sum(1 for v in verdicts if v.status == VerdictStatus.SKIP),
        }

        base_result = GroundingResult(
            original_response=original_response,
            grounded_response=original_response,
            claims_total=len(verdicts),
            claims_verified=counts["verified"],
            claims_refuted=counts["refuted"],
            claims_unverified=counts["unverified"],
            claims_skipped=counts["skipped"],
            verdicts=verdicts,
        )

        if self.mode == GroundingMode.MONITOR:
            return base_result

        if self.mode == GroundingMode.STRICT:
            return self._apply_strict(base_result, verdicts)

        # ENFORCE mode
        return self._apply_enforce(base_result, verdicts, original_response)

    def _apply_strict(self, result: GroundingResult, verdicts: List[Verdict]) -> GroundingResult:
        """Block entire response if any claim is REFUTED or UNVERIFIED."""
        has_issues = any(
            v.status in (VerdictStatus.REFUTED, VerdictStatus.UNVERIFIED)
            for v in verdicts
        )

        if has_issues:
            result.grounded_response = (
                "Ответ не может быть предоставлен, так как не все утверждения "
                "подтверждены клиническими рекомендациями Минздрава РФ."
            )
            result.disclaimers.append(
                "Ответ заблокирован режимом strict: обнаружены неподтверждённые утверждения."
            )

        return result

    def _apply_enforce(
        self,
        result: GroundingResult,
        verdicts: List[Verdict],
        original_response: str,
    ) -> GroundingResult:
        """Remove REFUTED/UNVERIFIED sentences, add sources for VERIFIED."""
        sentences = _split_sentences(original_response)

        # Build verdict map: find which sentences are affected
        # Map each verdict to its original_sentence for matching
        refuted_sentences: Set[int] = set()
        unverified_sentences: Set[int] = set()
        sources_by_sentence: dict = {}  # sentence_idx -> source string

        for verdict in verdicts:
            orig_sent = ""
            for claim in [verdict]:  # Use verdict which has claim_text
                # Find the matching sentence
                for idx, sent in enumerate(sentences):
                    # Try matching via verdict's evidence original_sentence
                    # or via claim_text substring
                    if verdict.claim_text and verdict.claim_text.lower()[:40] in sent.lower():
                        if verdict.status == VerdictStatus.REFUTED:
                            refuted_sentences.add(idx)
                        elif verdict.status == VerdictStatus.UNVERIFIED:
                            unverified_sentences.add(idx)
                        elif verdict.status == VerdictStatus.VERIFIED and verdict.evidence:
                            source = f"{verdict.evidence.source_path}"
                            sources_by_sentence[idx] = source
                            if source not in result.sources_cited:
                                result.sources_cited.append(source)
                        break

        # Reconstruct response
        output_parts = []
        for idx, sentence in enumerate(sentences):
            if idx in refuted_sentences:
                continue  # Remove refuted
            if idx in unverified_sentences:
                continue  # Remove unverified
            if idx in sources_by_sentence:
                output_parts.append(f"{sentence} [Источник: {sources_by_sentence[idx]}]")
            else:
                output_parts.append(sentence)

        # Add disclaimers
        disclaimers = []
        if result.claims_refuted > 0:
            disclaimers.append(
                f"Внимание: {result.claims_refuted} утверждение(й) было удалено, "
                "так как они противоречат клиническим рекомендациям."
            )
        if result.claims_unverified > 0:
            disclaimers.append(
                "Примечание: некоторые утверждения не удалось подтвердить "
                "по доступным клиническим рекомендациям Минздрава РФ."
            )

        result.disclaimers = disclaimers

        # Build final response
        grounded = " ".join(output_parts)
        if disclaimers:
            grounded += "\n\n---\n" + "\n".join(disclaimers)
        if result.sources_cited:
            grounded += "\n\nИсточники: " + ", ".join(result.sources_cited)

        result.grounded_response = grounded
        return result
