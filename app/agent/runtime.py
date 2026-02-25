"""
OpenAI Agent SDK runtime (DEPRECATED).

Uses OpenAI API with function calling.
All tool calls are intercepted and routed through Tool Proxy.

DEPRECATED: Use LangGraphAgentRuntime from app.agent.langgraph_runtime instead.
This module is kept for backward compatibility only.

Reference:
- https://platform.openai.com/docs/guides/function-calling
"""
import warnings
warnings.warn(
    "OpenAIAgentRuntime is deprecated. Use LangGraphAgentRuntime instead.",
    DeprecationWarning,
    stacklevel=2,
)
import json
import structlog
from typing import Any, Dict, List, Optional
from openai import AsyncOpenAI
from app.config import settings
from app.observability import metrics

logger = structlog.get_logger()


class OpenAIAgentRuntime:
    """
    Wrapper for OpenAI API with function calling.

    Uses the OpenAI Python SDK for tool calling.
    """

    def __init__(self, tool_proxy, tool_registry):
        self.tool_proxy = tool_proxy
        self.tool_registry = tool_registry
        self.client: Optional[AsyncOpenAI] = None

    async def initialize(self):
        """
        Initialize OpenAI client.

        Requires OPENAI_API_KEY to be set.
        """
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required. "
                "Set OPENAI_API_KEY environment variable to use the OpenAI API."
            )

        try:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            logger.info("OpenAI API initialized", model=settings.openai_model)
        except Exception as e:
            logger.error("Failed to initialize OpenAI API", exc_info=e)
            raise

    async def run(
        self,
        user_message: str,
        session_id: str,
        trace_id: str,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Run agent with user message.

        Returns:
            {
                'message': str,  # Agent's response
                'tool_calls': List[str],  # TOOL_CALL_IDs used
                'status': 'success' | 'error'
            }
        """
        logger.info(
            "Agent run started",
            session_id=session_id,
            trace_id=trace_id,
        )

        context = context or {}

        try:
            # Get available tools in OpenAI format
            tools = self.tool_registry.to_openai_format()

            response = await self._real_agent_run(
                user_message=user_message,
                tools=tools,
                session_id=session_id,
                trace_id=trace_id,
                context=context,
                history=history
            )

            # Get TOOL_CALL_IDs for output rails verification
            tool_call_ids = self.tool_proxy.get_tool_call_ids(session_id, trace_id)

            return {
                'message': response['message'],
                'tool_calls': tool_call_ids,
                'status': 'success'
            }

        except Exception as e:
            logger.error("Agent run failed", exc_info=e, trace_id=trace_id)
            return {
                'message': "Произошла ошибка при обработке вашего запроса.",
                'tool_calls': [],
                'status': 'error'
            }

    async def _real_agent_run(
        self,
        user_message: str,
        tools: List[Dict],
        session_id: str,
        trace_id: str,
        context: Dict[str, Any],
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Real agent run using OpenAI API with function calling.

        Implements agentic loop:
        1. Send message to OpenAI
        2. If OpenAI wants to use tools, execute them via Tool Proxy
        3. Send tool results back to OpenAI
        4. Repeat until OpenAI responds with text
        """
        logger.info("Real API agent run", message=user_message[:100])

        # Build messages with conversation history
        messages = []
        if history:
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        max_iterations = 10  # Prevent infinite loops

        for iteration in range(max_iterations):
            logger.debug(f"Agent iteration {iteration + 1}/{max_iterations}")

            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )

            message = response.choices[0].message

            # Check if OpenAI wants to use tools
            if message.tool_calls:
                logger.info(f"OpenAI requesting {len(message.tool_calls)} tool(s)")

                # Add assistant's message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                })

                # Execute tools via Tool Proxy
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name

                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse tool arguments: {e}")
                        tool_args = {}

                    logger.info(f"Executing tool: {tool_name}", args=tool_args)

                    # Execute tool via Tool Proxy
                    result = await self.tool_proxy.call(
                        tool_name=tool_name,
                        args=tool_args,
                        session_id=session_id,
                        trace_id=trace_id
                    )

                    # Add tool result to messages
                    tool_result_content = (
                        json.dumps(result['result']) if result['status'] == 'success'
                        else f"Error: {result['error']}"
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": tool_result_content
                    })

                # Continue loop to get OpenAI's next response
                continue

            # OpenAI responded with text - we're done
            else:
                text_content = message.content or "Я не уверен, как ответить на это."
                return {'message': text_content}

        # Max iterations reached
        logger.warning(f"Max iterations ({max_iterations}) reached")
        return {'message': "Извините, но я достиг лимита обработки для этого запроса."}
