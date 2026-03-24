"""
Claim Deduplicator — removes semantically equivalent claims.

Uses OpenAI embeddings to compute pairwise cosine similarity and groups
claims with similarity >= threshold, keeping the highest-confidence claim.
"""
from typing import List

import structlog

from app.grounding.models import Claim

logger = structlog.get_logger()

DEDUP_THRESHOLD = 0.92
MIN_CLAIMS_FOR_DEDUP = 6


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class ClaimDeduplicator:
    """Deduplicates semantically equivalent claims using embeddings."""

    def __init__(self, embeddings):
        """
        Args:
            embeddings: LangChain embeddings instance (e.g. OpenAIEmbeddings).
        """
        self.embeddings = embeddings

    async def deduplicate(self, claims: List[Claim]) -> List[Claim]:
        """
        Remove semantically duplicate claims.

        For lists <= MIN_CLAIMS_FOR_DEDUP, skip dedup (not worth the overhead).
        For larger lists, embed each claim and group by cosine similarity.
        """
        if len(claims) <= MIN_CLAIMS_FOR_DEDUP:
            return claims

        try:
            texts = [c.text for c in claims]
            vectors = await self.embeddings.aembed_documents(texts)

            # Union-Find for grouping
            parent = list(range(len(claims)))

            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            def union(x, y):
                px, py = find(x), find(y)
                if px != py:
                    parent[px] = py

            # Compare all pairs
            for i in range(len(claims)):
                for j in range(i + 1, len(claims)):
                    sim = _cosine_similarity(vectors[i], vectors[j])
                    if sim >= DEDUP_THRESHOLD:
                        union(i, j)

            # Group claims by cluster, keep highest confidence
            groups = {}
            for i, claim in enumerate(claims):
                root = find(i)
                if root not in groups:
                    groups[root] = []
                groups[root].append(claim)

            deduped = []
            for group in groups.values():
                best = max(group, key=lambda c: c.confidence)
                deduped.append(best)

            removed = len(claims) - len(deduped)
            if removed > 0:
                logger.info("Claims deduplicated", original=len(claims), deduplicated=len(deduped), removed=removed)

            return deduped

        except Exception as e:
            logger.warning("Claim deduplication failed, returning original claims", error=str(e))
            return claims
