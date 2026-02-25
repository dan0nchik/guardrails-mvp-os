"""FastAPI application entry point."""
import asyncio
import structlog
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any
import uuid

from app.config import settings
from app.observability import setup_logging, metrics
from app.sessions import SessionStore
from app.guardrails.runtime import GuardrailsRuntime
from app.utils.pii_detector import PIIDetector
from app.utils.safety_detector import SafetyDetector
from app.utils.rail_generator import RailGenerator

# Setup logging
logger = structlog.get_logger()
setup_logging()


class GuardrailsConfigRequest(BaseModel):
    """Guardrails configuration in request."""
    enabled: bool = True
    monitor_only: bool = False
    toggles: Dict[str, bool] = Field(default_factory=dict)


class HistoryMessage(BaseModel):
    """Single message in conversation history."""
    role: Literal['user', 'assistant']
    content: str


class ChatRequest(BaseModel):
    """Chat request schema."""
    session_id: str = Field(..., description="Session ID")
    user_message: str = Field(..., min_length=1, max_length=10000)
    agent_profile: str = Field(default="default", description="Agent profile to use")
    history: Optional[List[HistoryMessage]] = Field(default=None, description="Conversation history")
    guardrails: Optional[GuardrailsConfigRequest] = None


class RailEvent(BaseModel):
    """Rail event schema."""
    railName: str
    stage: Literal['input', 'execution', 'output']
    severity: Literal['info', 'warn', 'block']
    reason: str
    details: Optional[Dict[str, Any]] = None


class DynamicRuleDetail(BaseModel):
    """Detail of a single dynamic guardrail rule."""
    rule_id: str = ''
    domain: str = ''
    rule_type: str = ''
    description: str = ''
    severity: str = 'medium'


class GeneratedRails(BaseModel):
    """Generated rails schema."""
    profileId: str
    summary: str
    config: Optional[str] = None
    rules: Optional[List[DynamicRuleDetail]] = None
    new_rules: Optional[List[DynamicRuleDetail]] = None


class ChatResponse(BaseModel):
    """Chat response schema."""
    assistant_message: str
    status: Literal['ok', 'refused', 'escalated']
    trace_id: str
    tool_calls: list[str] = Field(default_factory=list, description="List of TOOL_CALL_IDs")
    rail_events: List[RailEvent] = Field(default_factory=list, description="Rail events triggered")
    generated_rails: Optional[GeneratedRails] = Field(default=None, description="Dynamically generated rails")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Guardrails MVP", env=settings.env, llm_provider=settings.llm_provider)

    # Create agent workspace directory
    workspace = Path(settings.agent_workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    logger.info("Agent workspace ready", path=str(workspace))

    # Initialize components
    app.state.session_store = SessionStore()
    app.state.guardrails = GuardrailsRuntime()
    app.state.pii_detector = PIIDetector()
    app.state.safety_detector = SafetyDetector()
    app.state.rail_generator = RailGenerator()

    await app.state.session_store.connect()
    await app.state.guardrails.initialize()
    await app.state.rail_generator.initialize()

    logger.info("Application started successfully")

    yield

    # Cleanup
    logger.info("Shutting down application")
    await app.state.session_store.disconnect()


app = FastAPI(
    title="Guardrails MVP",
    description="Model-agnostic Agent + Guardrails (NeMo/LangChain) + Dynamic Rules",
    version="0.2.0",
    lifespan=lifespan
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error("Unhandled exception", exc_info=exc, path=request.url.path)
    metrics.errors_total.inc()

    return JSONResponse(
        status_code=500,
        content={
            "error": "Внутренняя ошибка сервера",
            "trace_id": str(uuid.uuid4())
        }
    )


class RuntimeConfigUpdate(BaseModel):
    """Runtime config update request."""
    guardrails_backend: Optional[Literal['langchain', 'nemo', 'none']] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


@app.get("/config")
async def get_config(req: Request):
    """Get current runtime configuration."""
    return {
        "guardrails_backend": settings.guardrails_backend,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "available_backends": ["langchain", "nemo", "none"],
        "available_providers": [
            {"id": "openai", "models": ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"]}
        ],
    }


@app.post("/config")
async def set_config(update: RuntimeConfigUpdate, req: Request):
    """Update runtime configuration (switch backend/LLM on the fly)."""
    guardrails: GuardrailsRuntime = req.app.state.guardrails

    if update.guardrails_backend is not None:
        await guardrails.switch_backend(update.guardrails_backend)

    if update.llm_provider is not None or update.llm_model is not None:
        provider = update.llm_provider or settings.llm_provider
        model = update.llm_model or settings.llm_model
        await guardrails.switch_llm(provider, model)

    return {
        "guardrails_backend": settings.guardrails_backend,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "available_backends": ["langchain", "nemo", "none"],
        "available_providers": [
            {"id": "openai", "models": ["gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini"]}
        ],
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "env": settings.env,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "guardrails_backend": settings.guardrails_backend,
        "dynamic_rails": settings.dynamic_rails_enabled,
    }


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Metrics disabled")

    from prometheus_client import generate_latest
    return generate_latest()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """
    Main chat endpoint.

    Flow:
    1. Parallel: PII/safety check + dynamic rails classification
    2. Run through guardrails backend → agent → output check
    3. Return response with audit trail + dynamic rules
    """
    trace_id = str(uuid.uuid4())

    logger.info(
        "Chat request received",
        trace_id=trace_id,
        session_id=request.session_id,
        profile=request.agent_profile
    )

    try:
        rail_events = []
        status = 'ok'
        generated_rails = None

        # Get guardrails config from request or use defaults
        guardrails_config = request.guardrails
        pii_enabled = guardrails_config.toggles.get('input.pii', True) if guardrails_config else True
        safety_enabled = guardrails_config.toggles.get('output.safety', True) if guardrails_config else True
        monitor_only = guardrails_config.monitor_only if guardrails_config else False

        # Build history
        history = []
        if request.history:
            history = [{"role": m.role, "content": m.content} for m in request.history]

        # Load session
        session_store: SessionStore = req.app.state.session_store
        session_state = await session_store.get_session(request.session_id)

        # Parallel step: PII/safety checks + dynamic rails generation
        rail_generator: RailGenerator = req.app.state.rail_generator

        async def run_pii_safety():
            """Run PII and safety checks."""
            events = []

            if pii_enabled:
                pii_detector: PIIDetector = req.app.state.pii_detector
                pii_detections = pii_detector.detect(request.user_message)
                if pii_detections:
                    severity = 'warn' if monitor_only else 'block'
                    for detection in pii_detections:
                        events.append(RailEvent(
                            railName='input.pii',
                            stage='input',
                            severity=severity,
                            reason=detection['description'],
                            details={
                                'pii_type': detection['type'],
                                'snippet': detection['snippet'][:20] + '...' if len(detection['snippet']) > 20 else detection['snippet']
                            }
                        ))
                    if not monitor_only:
                        return events, True  # blocked

            if safety_enabled:
                safety_detector: SafetyDetector = req.app.state.safety_detector
                safety_check = safety_detector.check_input(request.user_message)
                if not safety_check['safe']:
                    severity = 'warn' if monitor_only else 'block'
                    for detection in safety_check['detections']:
                        events.append(RailEvent(
                            railName='input.safety',
                            stage='input',
                            severity=severity,
                            reason=detection['description'],
                            details={
                                'category': detection['category'],
                                'snippet': detection['snippet']
                            }
                        ))
                    if not monitor_only and safety_check['should_block']:
                        return events, True  # blocked

            return events, False

        async def run_dynamic_rails():
            """Generate dynamic rails."""
            return await rail_generator.generate(
                user_message=request.user_message,
                session_state=session_state,
                history=history,
            )

        # Run in parallel
        pii_safety_task = asyncio.create_task(run_pii_safety())
        rails_task = asyncio.create_task(run_dynamic_rails())

        (input_events, input_blocked), generated = await asyncio.gather(
            pii_safety_task, rails_task
        )

        rail_events.extend(input_events)

        # Process generated rails
        if generated:
            rules_list = None
            new_rules_list = None

            if generated.get('rules'):
                rules_list = [
                    DynamicRuleDetail(
                        rule_id=r.get('rule_id', ''),
                        domain=r.get('domain', ''),
                        rule_type=r.get('rule_type', ''),
                        description=r.get('description', ''),
                        severity=r.get('severity', 'medium'),
                    )
                    for r in generated['rules']
                ]

            if generated.get('new_rules'):
                new_rules_list = [
                    DynamicRuleDetail(
                        rule_id=r.get('rule_id', ''),
                        domain=r.get('domain', ''),
                        rule_type=r.get('rule_type', ''),
                        description=r.get('description', ''),
                        severity=r.get('severity', 'medium'),
                    )
                    for r in generated['new_rules']
                ]

            generated_rails = GeneratedRails(
                profileId=generated.get('profileId', ''),
                summary=generated.get('summary', ''),
                config=generated.get('config'),
                rules=rules_list,
                new_rules=new_rules_list,
            )

            # Save dynamic rules in session state
            if generated.get('rules'):
                session_state['dynamic_rules'] = generated['rules']

            logger.info("Generated dynamic rails", profile_id=generated_rails.profileId, trace_id=trace_id)

        # Handle input block
        if input_blocked:
            block_reason = (
                "Я не могу обработать это сообщение, так как оно содержит "
                "конфиденциальные персональные данные или небезопасный контент."
            )

            # Check if PII or safety
            has_pii = any(e.railName == 'input.pii' for e in rail_events)
            if has_pii:
                block_reason = (
                    "Я не могу обработать это сообщение, так как оно содержит "
                    "конфиденциальные персональные данные. Пожалуйста, удалите "
                    "номера банковских карт, номера документов или другие "
                    "персональные данные и попробуйте снова."
                )
            else:
                block_reason = (
                    "Я не могу помочь с запросами, связанными с насилием, "
                    "нелегальной деятельностью, причинением вреда себе или другим "
                    "опасным контентом. Если у вас есть другие вопросы, я с радостью помогу!"
                )

            logger.warning("Input blocked", trace_id=trace_id)
            metrics.requests_total.labels(status='refused', profile=request.agent_profile).inc()

            return ChatResponse(
                assistant_message=block_reason,
                status='refused',
                trace_id=trace_id,
                tool_calls=[],
                rail_events=rail_events,
                generated_rails=generated_rails,
            )

        # Run through guardrails runtime (agent + backend guardrails)
        guardrails: GuardrailsRuntime = req.app.state.guardrails

        result = await guardrails.generate(
            user_message=request.user_message,
            session_state=session_state,
            agent_profile=request.agent_profile,
            trace_id=trace_id,
            history=history,
        )

        # Check output safety if enabled
        assistant_message = result['message']
        final_status = result['status']

        if safety_enabled:
            output_safety_check = req.app.state.safety_detector.check_output(assistant_message)

            if not output_safety_check['safe']:
                severity = 'warn' if monitor_only else 'block'
                for detection in output_safety_check['detections']:
                    rail_events.append(RailEvent(
                        railName='output.safety',
                        stage='output',
                        severity=severity,
                        reason=detection['description'],
                        details={
                            'category': detection['category'],
                            'snippet': detection.get('snippet', 'N/A')
                        }
                    ))

                if not monitor_only and output_safety_check['should_block']:
                    logger.warning("Unsafe content in output, blocking", trace_id=trace_id)
                    assistant_message = "Извините, но я не могу предоставить эту информацию, так как она может быть опасной. Могу ли я помочь вам с чем-то другим?"
                    final_status = 'refused'
                    metrics.refusals_total.inc()

        # Update session
        await session_store.update_session(
            request.session_id,
            result.get('session_state', session_state)
        )

        metrics.requests_total.labels(
            status=final_status,
            profile=request.agent_profile
        ).inc()

        return ChatResponse(
            assistant_message=assistant_message,
            status=final_status,
            trace_id=trace_id,
            tool_calls=result.get('tool_calls', []),
            rail_events=rail_events,
            generated_rails=generated_rails,
        )

    except Exception as e:
        logger.error("Chat request failed", trace_id=trace_id, exc_info=e)
        metrics.errors_total.inc()
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")


@app.post("/oauth/callback")
async def oauth_callback(code: str, state: Optional[str] = None):
    """OAuth callback (deprecated)."""
    logger.info("OAuth callback received (deprecated)", code_present=bool(code))
    return {"status": "ok", "message": "OAuth flow not needed"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
