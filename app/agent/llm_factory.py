"""
LLM Factory: model-agnostic chat model creation.

Supports OpenAI, Anthropic, Ollama, and OpenAI-compatible (vLLM) providers.
Respects HTTP_PROXY/HTTPS_PROXY environment variables for all providers.
"""
import httpx
import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from app.config import settings

logger = structlog.get_logger()


def _get_openai_http_client() -> httpx.AsyncClient | None:
    """Create an httpx client with proxy support for OpenAI."""
    proxy_url = settings.https_proxy or settings.http_proxy
    if not proxy_url:
        return None
    logger.info("Using proxy for OpenAI", proxy=proxy_url.split('@')[-1])
    return httpx.AsyncClient(proxy=proxy_url)


def create_chat_model(
    provider: str,
    model: str,
    api_key: str = '',
    base_url: str = '',
    temperature: float = 0.0,
) -> BaseChatModel:
    """
    Create a LangChain chat model for the given provider.

    Args:
        provider: One of 'openai', 'anthropic', 'ollama', 'vllm'
        model: Model name (e.g. 'gpt-4o', 'claude-sonnet-4-20250514')
        api_key: API key (required for openai/anthropic)
        base_url: Custom endpoint URL (for ollama/vllm)
        temperature: Sampling temperature

    Returns:
        BaseChatModel instance
    """
    if provider == 'openai':
        from langchain_openai import ChatOpenAI
        kwargs = {
            'model': model,
            'temperature': temperature,
        }
        if api_key:
            kwargs['api_key'] = api_key
        if base_url:
            kwargs['base_url'] = base_url
        http_client = _get_openai_http_client()
        if http_client:
            kwargs['http_async_client'] = http_client
        llm = ChatOpenAI(**kwargs)
        logger.info("Created OpenAI chat model", model=model)
        return llm

    elif provider == 'anthropic':
        from langchain_anthropic import ChatAnthropic
        kwargs = {
            'model': model,
            'temperature': temperature,
        }
        if api_key:
            kwargs['api_key'] = api_key
        llm = ChatAnthropic(**kwargs)
        logger.info("Created Anthropic chat model", model=model)
        return llm

    elif provider == 'ollama':
        from langchain_community.chat_models import ChatOllama
        kwargs = {
            'model': model,
            'temperature': temperature,
        }
        if base_url:
            kwargs['base_url'] = base_url
        llm = ChatOllama(**kwargs)
        logger.info("Created Ollama chat model", model=model, base_url=base_url)
        return llm

    elif provider == 'vllm':
        # vLLM exposes OpenAI-compatible API
        from langchain_openai import ChatOpenAI
        if not base_url:
            base_url = 'http://localhost:8000/v1'
        kwargs = {
            'model': model,
            'temperature': temperature,
            'base_url': base_url,
        }
        if api_key:
            kwargs['api_key'] = api_key
        else:
            kwargs['api_key'] = 'EMPTY'  # vLLM requires a non-empty key
        llm = ChatOpenAI(**kwargs)
        logger.info("Created vLLM chat model", model=model, base_url=base_url)
        return llm

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
