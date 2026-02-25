"""
HTTP client utilities with proxy support.

For ChatGPT API and other external services.
"""
import httpx
from typing import Optional, Dict, Any
from app.config import settings
import structlog

logger = structlog.get_logger()


def get_httpx_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """
    Create httpx client with proxy support.

    Reads HTTP_PROXY and HTTPS_PROXY from settings.

    Example proxy format:
        http://user:password@host:port
        http://newuser:Lwtrmphgd0gtmLHskVHzTA==@167.224.64.184:3128
    """
    proxies = {}

    if settings.http_proxy:
        proxies['http://'] = settings.http_proxy
        logger.info("HTTP proxy configured", proxy=settings.http_proxy.split('@')[-1])

    if settings.https_proxy:
        proxies['https://'] = settings.https_proxy
        logger.info("HTTPS proxy configured", proxy=settings.https_proxy.split('@')[-1])

    return httpx.AsyncClient(
        proxies=proxies if proxies else None,
        timeout=timeout,
        follow_redirects=True
    )


async def fetch_with_proxy(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0
) -> httpx.Response:
    """
    Fetch URL with proxy support.

    Args:
        url: Target URL
        method: HTTP method (GET, POST, etc.)
        headers: Optional headers
        json: Optional JSON body
        timeout: Request timeout in seconds

    Returns:
        httpx.Response object
    """
    async with get_httpx_client(timeout=timeout) as client:
        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            json=json
        )
        response.raise_for_status()
        return response


# Example: ChatGPT API call with proxy
async def call_chatgpt_api(
    prompt: str,
    api_key: str,
    model: str = "gpt-4",
    max_tokens: int = 1000
) -> Dict[str, Any]:
    """
    Call ChatGPT API through proxy.

    Args:
        prompt: User prompt
        api_key: OpenAI API key
        model: Model to use
        max_tokens: Max tokens in response

    Returns:
        API response as dict
    """
    url = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens
    }

    logger.info("Calling ChatGPT API", model=model, proxy_enabled=bool(settings.http_proxy or settings.https_proxy))

    response = await fetch_with_proxy(
        url=url,
        method="POST",
        headers=headers,
        json=payload,
        timeout=60.0
    )

    return response.json()
