"""
LangGraph Agent Runtime.

Model-agnostic agent runtime using LangGraph StateGraph.
Replaces the OpenAI-specific runtime with support for any LangChain-compatible model.
"""
import json
import structlog
from typing import Any, Dict, List, Optional, Annotated, TypedDict, Sequence
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
from langgraph.graph import StateGraph, END

from app.config import settings
from app.agent.llm_factory import create_chat_model
from app.observability import metrics

logger = structlog.get_logger()


class AgentState(TypedDict):
    """State for the LangGraph agent."""
    messages: Annotated[Sequence[BaseMessage], lambda a, b: list(a) + list(b)]
    session_id: str
    trace_id: str
    tool_call_ids: list
    iteration: int


class LangGraphAgentRuntime:
    """
    LangGraph-based agent runtime.

    Same interface as OpenAIAgentRuntime:
        run(user_message, session_id, trace_id, context, history) -> {message, tool_calls, status}
    """

    MAX_ITERATIONS = 10

    def __init__(self, tool_proxy, tool_registry):
        self.tool_proxy = tool_proxy
        self.tool_registry = tool_registry
        self.llm = None
        self.graph = None

    async def initialize(self):
        """Initialize the LLM and build the LangGraph."""
        # Resolve API key: prefer llm_api_key, fallback to openai_api_key
        api_key = settings.llm_api_key or settings.openai_api_key

        self.llm = create_chat_model(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=api_key,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
        )

        # Bind tools to the LLM
        langchain_tools = self.tool_registry.to_langchain_tools()
        if langchain_tools:
            self.llm = self.llm.bind_tools(langchain_tools)

        # Build the graph
        self.graph = self._build_graph()

        logger.info(
            "LangGraph agent initialized",
            provider=settings.llm_provider,
            model=settings.llm_model,
        )

    async def switch_llm(self, provider: str, model: str):
        """Switch LLM provider/model at runtime."""
        api_key = settings.llm_api_key or settings.openai_api_key
        self.llm = create_chat_model(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
        )
        langchain_tools = self.tool_registry.to_langchain_tools()
        if langchain_tools:
            self.llm = self.llm.bind_tools(langchain_tools)
        self.graph = self._build_graph()
        logger.info("LLM switched at runtime", provider=provider, model=model)

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph with agent and tools nodes."""
        graph = StateGraph(AgentState)

        graph.add_node("agent", self._agent_node)
        graph.add_node("tools", self._tools_node)

        graph.set_entry_point("agent")

        graph.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "tools": "tools",
                "end": END,
            }
        )
        graph.add_edge("tools", "agent")

        return graph.compile()

    def _should_continue(self, state: AgentState) -> str:
        """Decide whether to call tools or finish."""
        messages = state["messages"]
        if not messages:
            return "end"

        last_message = messages[-1]

        # Check iteration limit
        if state.get("iteration", 0) >= self.MAX_ITERATIONS:
            logger.warning("Max iterations reached", iteration=state["iteration"])
            return "end"

        # If the last message has tool calls, route to tools
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        return "end"

    async def _agent_node(self, state: AgentState) -> dict:
        """Call the LLM."""
        messages = list(state["messages"])
        response = await self.llm.ainvoke(messages)
        iteration = state.get("iteration", 0) + 1
        return {"messages": [response], "iteration": iteration}

    async def _tools_node(self, state: AgentState) -> dict:
        """Execute tool calls via ToolProxy."""
        messages = list(state["messages"])
        last_message = messages[-1]

        tool_messages = []
        tool_call_ids = list(state.get("tool_call_ids", []))

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            call_id = tool_call["id"]

            logger.info(f"Executing tool: {tool_name}", args=tool_args)

            result = await self.tool_proxy.call(
                tool_name=tool_name,
                args=tool_args,
                session_id=state["session_id"],
                trace_id=state["trace_id"],
            )

            if result["status"] == "success":
                content = json.dumps(result["result"])
            else:
                content = f"Error: {result['error']}"

            tool_messages.append(
                ToolMessage(content=content, tool_call_id=call_id, name=tool_name)
            )

            if result.get("tool_call_id"):
                tool_call_ids.append(result["tool_call_id"])

        return {"messages": tool_messages, "tool_call_ids": tool_call_ids}

    async def run(
        self,
        user_message: str,
        session_id: str,
        trace_id: str,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Run agent with user message.

        Returns:
            {
                'message': str,
                'tool_calls': List[str],
                'status': 'success' | 'error'
            }
        """
        logger.info("LangGraph agent run started", session_id=session_id, trace_id=trace_id)

        try:
            # Build messages
            messages: List[BaseMessage] = []

            # Add system message
            messages.append(SystemMessage(content=(
                "Ты — полезный ИИ-ассистент с доступом к инструментам. "
                "Всегда указывай TOOL_CALL_ID при упоминании результатов инструментов. "
                "Отвечай на русском языке."
            )))

            # Add conversation history
            if history:
                for msg in history:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        messages.append(AIMessage(content=msg["content"]))

            # Add current user message
            messages.append(HumanMessage(content=user_message))

            # Run the graph
            initial_state: AgentState = {
                "messages": messages,
                "session_id": session_id,
                "trace_id": trace_id,
                "tool_call_ids": [],
                "iteration": 0,
            }

            result_state = await self.graph.ainvoke(initial_state)

            # Extract final message
            final_messages = result_state["messages"]
            assistant_message = "Я не уверен, как ответить на это."

            # Find the last AI message
            for msg in reversed(final_messages):
                if isinstance(msg, AIMessage) and msg.content:
                    assistant_message = msg.content
                    break

            # Get tool call IDs
            tool_call_ids = self.tool_proxy.get_tool_call_ids(session_id, trace_id)

            return {
                "message": assistant_message,
                "tool_calls": tool_call_ids,
                "status": "success",
            }

        except Exception as e:
            logger.error("LangGraph agent run failed", exc_info=e, trace_id=trace_id)
            return {
                "message": "Произошла ошибка при обработке вашего запроса.",
                "tool_calls": [],
                "status": "error",
            }
