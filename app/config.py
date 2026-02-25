"""Configuration management for Guardrails MVP."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False
    )

    # Environment
    env: Literal['development', 'production'] = 'development'
    debug: bool = False

    # API
    api_host: str = '0.0.0.0'
    api_port: int = 8000

    # LLM Provider (model-agnostic)
    llm_provider: Literal['openai', 'anthropic', 'ollama', 'vllm'] = 'openai'
    llm_model: str = 'gpt-4o'
    llm_api_key: str = ''
    llm_base_url: str = ''  # For ollama/vllm custom endpoints
    llm_temperature: float = 0.0

    # OpenAI API (backward compat fallback)
    openai_api_key: str = ''
    openai_model: str = 'gpt-4o'

    # Guardrails backend
    guardrails_backend: Literal['nemo', 'langchain', 'none'] = 'langchain'

    # Dynamic rails classifier
    classifier_model: str = ''  # Default: gpt-4o-mini
    dynamic_rails_enabled: bool = True
    dynamic_rails_max_rules_per_session: int = 50

    # Redis
    redis_url: str = 'redis://localhost:6379/0'
    redis_session_ttl: int = 3600

    # Postgres
    database_url: str

    # Tool Proxy
    tool_max_calls_per_request: int = 10
    tool_rate_limit_per_min: int = 30
    tool_loop_breaker_threshold: int = 3
    tool_timeout_seconds: int = 15

    # Guardrails
    guardrails_profile: str = 'default'
    guardrails_mode: Literal['enforce', 'monitor'] = 'enforce'
    guardrails_max_regen: int = 1

    # Agent Workspace
    agent_workspace: str = './agent_workspace'

    # Observability
    log_level: str = 'INFO'
    metrics_enabled: bool = True
    prometheus_port: int = 9090

    # HTTP/HTTPS Proxy (optional)
    http_proxy: str = ''
    https_proxy: str = ''


# Global settings instance
settings = Settings()
