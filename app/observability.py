"""Observability: structured logging and metrics."""
import structlog
import logging
from prometheus_client import Counter, Histogram, Gauge
from app.config import settings


def setup_logging():
    """Configure structured logging with structlog."""
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper()),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if not settings.debug
            else structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class Metrics:
    """Prometheus metrics for the application."""

    def __init__(self):
        # Requests
        self.requests_total = Counter(
            'guardrails_requests_total',
            'Total number of chat requests',
            ['status', 'profile']
        )

        # Errors
        self.errors_total = Counter(
            'guardrails_errors_total',
            'Total number of errors'
        )

        # Guardrails
        self.input_blocked_total = Counter(
            'guardrails_input_blocked_total',
            'Input rails blocked',
            ['reason']
        )

        self.output_blocked_total = Counter(
            'guardrails_output_blocked_total',
            'Output rails blocked',
            ['reason']
        )

        self.regen_total = Counter(
            'guardrails_regen_total',
            'Regeneration attempts',
            ['reason']
        )

        self.refusals_total = Counter(
            'guardrails_refusals_total',
            'Safe refusals after regen failed'
        )

        # Tools
        self.tool_calls_total = Counter(
            'guardrails_tool_calls_total',
            'Total tool calls',
            ['tool_name', 'status']
        )

        self.tool_call_errors_total = Counter(
            'guardrails_tool_call_errors_total',
            'Tool call errors',
            ['tool_name', 'error_type']
        )

        self.tool_call_duration = Histogram(
            'guardrails_tool_call_duration_seconds',
            'Tool call duration',
            ['tool_name']
        )

        # Agent
        self.agent_duration = Histogram(
            'guardrails_agent_duration_seconds',
            'Agent execution duration',
            ['profile']
        )

        # Sessions
        self.active_sessions = Gauge(
            'guardrails_active_sessions',
            'Number of active sessions'
        )


# Global metrics instance
metrics = Metrics()
