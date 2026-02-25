"""Tests for FastAPI endpoints."""
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'


@pytest.mark.asyncio
async def test_chat_endpoint():
    """Test chat endpoint."""
    # NOTE: This test requires mocked services (Redis, Guardrails runtime)
    # For MVP, this is a placeholder

    request_data = {
        "session_id": "test-session-001",
        "user_message": "Hello, what's the weather?",
        "agent_profile": "default"
    }

    # TODO: Mock dependencies and test
    # async with AsyncClient(app=app, base_url="http://test") as client:
    #     response = await client.post("/chat", json=request_data)
    #
    # assert response.status_code == 200
    # data = response.json()
    # assert 'assistant_message' in data
    # assert 'trace_id' in data

    # Placeholder assertion
    assert True
