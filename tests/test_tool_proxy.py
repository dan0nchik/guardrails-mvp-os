"""Tests for Tool Proxy."""
import pytest
from app.tool_proxy.proxy import ToolProxy
from app.tool_proxy.registry import ToolRegistry
from app.tool_proxy.policies import ToolPolicy
from app.agent.tools import register_default_tools


@pytest.fixture
def tool_registry():
    """Create tool registry with default tools."""
    registry = ToolRegistry()
    register_default_tools(registry)
    return registry


@pytest.fixture
def tool_policy():
    """Create default tool policy."""
    return ToolPolicy(default_allow=True)


@pytest.fixture
def tool_proxy(tool_registry, tool_policy):
    """Create tool proxy."""
    return ToolProxy(tool_registry, tool_policy)


@pytest.mark.asyncio
async def test_tool_call_success(tool_proxy):
    """Test successful tool call."""
    result = await tool_proxy.call(
        tool_name='calculate',
        args={'expression': '2+2'},
        session_id='test-session',
        trace_id='test-trace'
    )

    assert result['status'] == 'success'
    assert result['tool_call_id'] is not None
    assert result['result'] is not None
    assert result['error'] is None


@pytest.mark.asyncio
async def test_tool_call_validation_error(tool_proxy):
    """Test tool call with invalid arguments."""
    result = await tool_proxy.call(
        tool_name='read_file',
        args={},  # Missing required 'path'
        session_id='test-session',
        trace_id='test-trace'
    )

    assert result['status'] == 'error'
    assert 'validation_error' in result['error']


@pytest.mark.asyncio
async def test_tool_not_found(tool_proxy):
    """Test calling non-existent tool."""
    result = await tool_proxy.call(
        tool_name='nonexistent_tool',
        args={},
        session_id='test-session',
        trace_id='test-trace'
    )

    assert result['status'] == 'error'
    assert 'Unknown tool' in result['error']


@pytest.mark.asyncio
async def test_tool_denylist(tool_registry):
    """Test tool denylist enforcement."""
    policy = ToolPolicy(
        denylist={'read_file'},
        default_allow=True
    )

    proxy = ToolProxy(tool_registry, policy)

    result = await proxy.call(
        tool_name='read_file',
        args={'path': 'test.txt'},
        session_id='test-session',
        trace_id='test-trace'
    )

    assert result['status'] == 'error'
    assert 'not allowed' in result['error']


@pytest.mark.asyncio
async def test_audit_trail(tool_proxy):
    """Test audit trail creation."""
    await tool_proxy.call(
        tool_name='calculate',
        args={'expression': '2+2'},
        session_id='test-session',
        trace_id='test-trace'
    )

    trail = tool_proxy.get_audit_trail('test-session', 'test-trace')

    assert len(trail) == 1
    assert trail[0]['tool_name'] == 'calculate'
    assert trail[0]['tool_call_id'] is not None


@pytest.mark.asyncio
async def test_get_tool_call_ids(tool_proxy):
    """Test getting TOOL_CALL_IDs."""
    # Make successful call
    result1 = await tool_proxy.call(
        tool_name='calculate',
        args={'expression': '10*5'},
        session_id='test-session',
        trace_id='test-trace'
    )

    # Make another successful call
    result2 = await tool_proxy.call(
        tool_name='calculate',
        args={'expression': '3+7'},
        session_id='test-session',
        trace_id='test-trace'
    )

    ids = tool_proxy.get_tool_call_ids('test-session', 'test-trace')

    assert len(ids) == 2
    assert result1['tool_call_id'] in ids
    assert result2['tool_call_id'] in ids
