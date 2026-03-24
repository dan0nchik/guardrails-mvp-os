"""Pydantic models for the Factual Grounding Layer."""
import uuid
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    FACTUAL = "factual"
    STATISTICAL = "statistical"
    RECOMMENDATION = "recommendation"
    TEMPORAL = "temporal"
    CAUSAL = "causal"


class VerdictStatus(str, Enum):
    VERIFIED = "verified"
    REFUTED = "refuted"
    UNVERIFIED = "unverified"
    SKIP = "skip"


class GroundingMode(str, Enum):
    ENFORCE = "enforce"
    MONITOR = "monitor"
    STRICT = "strict"


class Claim(BaseModel):
    """Atomic verifiable claim extracted from LLM response."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    text: str
    type: ClaimType = ClaimType.FACTUAL
    confidence: float = 0.0
    original_sentence: str = ""


class EvidenceResult(BaseModel):
    """Evidence found for a claim from source documents."""
    claim_id: str
    source_path: str
    section: str = ""
    passage: str
    relevance_score: float
    nli_status: str  # SUPPORTS / REFUTES / NOT_ENOUGH_INFO
    nli_confidence: float = 0.0


class Verdict(BaseModel):
    """Final verdict for a claim after evidence verification."""
    claim_id: str
    claim_text: str
    status: VerdictStatus
    evidence: Optional[EvidenceResult] = None
    confidence: float = 0.0
    reason: str = ""


class GroundingResult(BaseModel):
    """Full result of the grounding pipeline for one response."""
    original_response: str
    grounded_response: str
    claims_total: int = 0
    claims_verified: int = 0
    claims_refuted: int = 0
    claims_unverified: int = 0
    claims_skipped: int = 0
    verdicts: List[Verdict] = Field(default_factory=list)
    disclaimers: List[str] = Field(default_factory=list)
    sources_cited: List[str] = Field(default_factory=list)
    pipeline_duration_ms: float = 0.0
