"""Tool Registry: реестр доступных tools с pydantic schemas."""
from typing import Any, Callable, Dict, Optional, Type
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()


class ToolDefinition:
    """Definition of a tool with schema and executor."""

    def __init__(
        self,
        name: str,
        description: str,
        schema: Type[BaseModel],
        executor: Callable,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.description = description
        self.schema = schema
        self.executor = executor
        self.metadata = metadata or {}

    async def execute(self, args: Dict[str, Any]) -> Any:
        """Execute tool with validated args."""
        return await self.executor(**args)


class ToolRegistry:
    """
    Registry of all available tools.

    Tools MUST be registered here before use.
    """

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        schema: Type[BaseModel],
        executor: Callable,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Register a new tool."""
        if name in self.tools:
            logger.warning("Tool already registered, overwriting", tool_name=name)

        tool_def = ToolDefinition(
            name=name,
            description=description,
            schema=schema,
            executor=executor,
            metadata=metadata
        )

        self.tools[name] = tool_def
        logger.info("Tool registered", tool_name=name, description=description)

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name."""
        return self.tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self.tools.keys())

    def get_all_tools(self) -> Dict[str, ToolDefinition]:
        """Get all tool definitions."""
        return self.tools.copy()

    def to_openai_format(self) -> list[Dict[str, Any]]:
        """
        Export tools in OpenAI function calling format.

        See: https://platform.openai.com/docs/guides/function-calling
        """
        tools = []

        for tool in self.tools.values():
            # Convert pydantic schema to JSON schema
            json_schema = tool.schema.model_json_schema()

            # Remove $defs if present (OpenAI doesn't need them in most cases)
            if '$defs' in json_schema:
                del json_schema['$defs']

            # OpenAI format wraps schema in 'function' object
            tools.append({
                'type': 'function',
                'function': {
                    'name': tool.name,
                    'description': tool.description,
                    'parameters': json_schema
                }
            })

        return tools

    def to_langchain_tools(self) -> list:
        """
        Export tools as LangChain StructuredTool objects (schema-only).

        These are used for llm.bind_tools() — they provide schemas for the LLM
        to generate tool calls. Actual execution goes through ToolProxy.
        """
        from langchain_core.tools import StructuredTool

        tools = []
        for tool in self.tools.values():
            # Create a dummy function with the right signature for schema
            async def _placeholder(**kwargs):
                raise NotImplementedError("Execution goes through ToolProxy")

            structured_tool = StructuredTool.from_function(
                func=_placeholder,
                coroutine=_placeholder,
                name=tool.name,
                description=tool.description,
                args_schema=tool.schema,
            )
            tools.append(structured_tool)

        return tools

    def to_claude_format(self) -> list[Dict[str, Any]]:
        """
        Export tools in Claude SDK format (deprecated, kept for compatibility).

        See: https://platform.claude.com/docs/en/agent-sdk/python
        """
        tools = []

        for tool in self.tools.values():
            # Convert pydantic schema to JSON schema
            json_schema = tool.schema.model_json_schema()

            tools.append({
                'name': tool.name,
                'description': tool.description,
                'input_schema': json_schema
            })

        return tools
