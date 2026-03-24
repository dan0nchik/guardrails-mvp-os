"""
Grounding Pipeline — orchestrates the full claim-level verification chain.

Flow:
    draft_response → ClaimExtractor → ClaimDeduplicator → SourceBinder
    → ClaimVerifier → ReactionHandler → final_response

Graceful degradation: if any step fails, returns the original response.
"""
import time
from typing import Optional

import structlog

from app.config import settings
from app.grounding.models import GroundingMode, GroundingResult

logger = structlog.get_logger()


class GroundingPipeline:
    """Orchestrates all grounding components."""

    def __init__(self):
        self.claim_extractor = None
        self.claim_deduplicator = None
        self.source_binder = None
        self.claim_verifier = None
        self.reaction_handler = None
        self._initialized = False

    async def initialize(self):
        """Initialize all grounding components: LLM, embeddings, ChromaDB."""
        from langchain_openai import OpenAIEmbeddings

        from app.agent.llm_factory import create_chat_model
        from app.grounding.claim_deduplicator import ClaimDeduplicator
        from app.grounding.claim_extractor import ClaimExtractor
        from app.grounding.claim_verifier import ClaimVerifier
        from app.grounding.indexer import DocumentIndexer
        from app.grounding.reaction_handler import ReactionHandler
        from app.grounding.source_binder import SourceBinder

        api_key = settings.llm_api_key or settings.openai_api_key

        # Create LLM for grounding (claim extraction + NLI)
        grounding_model = settings.grounding_model or settings.llm_model
        llm = create_chat_model(
            provider=settings.llm_provider,
            model=grounding_model,
            api_key=api_key,
            base_url=settings.llm_base_url,
            temperature=0.0,
        )

        # Create embeddings
        embeddings = OpenAIEmbeddings(
            model=settings.grounding_embedding_model,
            api_key=api_key,
        )

        # Initialize document indexer
        indexer = DocumentIndexer(
            dataset_path=settings.grounding_dataset_path,
            persist_directory=settings.grounding_chroma_persist_dir,
            embedding_model=settings.grounding_embedding_model,
        )
        await indexer.initialize()

        # Wire up components
        self.claim_extractor = ClaimExtractor(llm=llm)
        self.claim_deduplicator = ClaimDeduplicator(embeddings=embeddings)
        self.source_binder = SourceBinder(
            indexer=indexer,
            llm=llm,
            relevance_threshold=settings.grounding_relevance_threshold,
            nli_threshold=settings.grounding_nli_threshold,
        )
        self.claim_verifier = ClaimVerifier()
        self.reaction_handler = ReactionHandler(mode=GroundingMode(settings.grounding_mode))

        self._initialized = True
        logger.info(
            "Grounding pipeline initialized",
            model=grounding_model,
            mode=settings.grounding_mode,
            embedding_model=settings.grounding_embedding_model,
        )

    async def ground(self, draft_response: str, trace_id: str) -> GroundingResult:
        """
        Run the full grounding pipeline on a draft response.

        Args:
            draft_response: The LLM's original response text.
            trace_id: Trace ID for logging.

        Returns:
            GroundingResult with grounded response and verdict details.
        """
        start_time = time.time()

        if not self._initialized:
            logger.warning("Grounding pipeline not initialized, returning original", trace_id=trace_id)
            return GroundingResult(
                original_response=draft_response,
                grounded_response=draft_response,
            )

        try:
            return await self._run_pipeline(draft_response, trace_id, start_time)
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("Grounding pipeline failed, returning original response",
                         exc_info=e, trace_id=trace_id, duration_ms=duration_ms)
            return GroundingResult(
                original_response=draft_response,
                grounded_response=draft_response,
                pipeline_duration_ms=duration_ms,
            )

    async def _run_pipeline(self, draft_response: str, trace_id: str, start_time: float) -> GroundingResult:
        """Internal pipeline execution with step-by-step logging."""
        # Step 1: Extract claims
        step_start = time.time()
        claims = await self.claim_extractor.extract(draft_response)
        logger.info("Step 1: Claims extracted",
                     trace_id=trace_id, count=len(claims),
                     duration_ms=round((time.time() - step_start) * 1000, 1))

        if not claims:
            duration_ms = (time.time() - start_time) * 1000
            return GroundingResult(
                original_response=draft_response,
                grounded_response=draft_response,
                pipeline_duration_ms=duration_ms,
            )

        # Cap claims count
        if len(claims) > settings.grounding_max_claims:
            claims = claims[:settings.grounding_max_claims]
            logger.info("Claims capped", trace_id=trace_id, max=settings.grounding_max_claims)

        # Step 2: Deduplicate claims
        step_start = time.time()
        claims = await self.claim_deduplicator.deduplicate(claims)
        logger.info("Step 2: Claims deduplicated",
                     trace_id=trace_id, count=len(claims),
                     duration_ms=round((time.time() - step_start) * 1000, 1))

        # Step 3: Bind evidence (parallel NLI)
        step_start = time.time()
        evidence_map = await self.source_binder.bind_all(claims)
        logger.info("Step 3: Evidence bound",
                     trace_id=trace_id,
                     found=sum(1 for v in evidence_map.values() if v),
                     duration_ms=round((time.time() - step_start) * 1000, 1))

        # Step 4: Verify claims
        step_start = time.time()
        verdicts = self.claim_verifier.verify_all(claims, evidence_map)
        logger.info("Step 4: Verdicts assigned",
                     trace_id=trace_id, count=len(verdicts),
                     duration_ms=round((time.time() - step_start) * 1000, 1))

        # Step 5: Apply reactions
        step_start = time.time()
        result = self.reaction_handler.apply(draft_response, verdicts)
        result.pipeline_duration_ms = (time.time() - start_time) * 1000
        logger.info("Step 5: Reactions applied",
                     trace_id=trace_id,
                     mode=self.reaction_handler.mode.value,
                     duration_ms=round((time.time() - step_start) * 1000, 1),
                     total_duration_ms=round(result.pipeline_duration_ms, 1))

        # Update metrics
        self._record_metrics(result)

        return result

    def _record_metrics(self, result: GroundingResult):
        """Record Prometheus metrics for grounding results."""
        try:
            from app.observability import metrics
            metrics.grounding_claims_total.labels(verdict="verified").inc(result.claims_verified)
            metrics.grounding_claims_total.labels(verdict="refuted").inc(result.claims_refuted)
            metrics.grounding_claims_total.labels(verdict="unverified").inc(result.claims_unverified)
            metrics.grounding_claims_total.labels(verdict="skip").inc(result.claims_skipped)
            metrics.grounding_pipeline_duration.observe(result.pipeline_duration_ms / 1000)
            if result.grounded_response != result.original_response:
                metrics.grounding_responses_modified.inc()
        except Exception:
            pass  # Metrics are best-effort
