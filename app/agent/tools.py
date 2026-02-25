"""
Agent tools: real working tools for the agent.

All file tools are sandboxed to the configured agent_workspace directory.
"""
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import httpx
import structlog
from pydantic import BaseModel, Field

from app.config import settings

logger = structlog.get_logger()


def _resolve_workspace_path(relative_path: str) -> Path:
    """
    Resolve a relative path within the workspace, preventing directory traversal.

    Raises ValueError if the path escapes the workspace.
    """
    workspace = Path(settings.agent_workspace).resolve()
    target = (workspace / relative_path).resolve()
    if not str(target).startswith(str(workspace)):
        raise ValueError(f"Path '{relative_path}' escapes the workspace")
    return target


# --- Schemas ---

class ReadFileArgs(BaseModel):
    """Arguments for read_file tool."""
    path: str = Field(..., description="File path relative to workspace")


class WriteFileArgs(BaseModel):
    """Arguments for write_file tool."""
    path: str = Field(..., description="File path relative to workspace")
    content: str = Field(..., description="Content to write to the file")


class ListDirectoryArgs(BaseModel):
    """Arguments for list_directory tool."""
    path: str = Field(default=".", description="Directory path relative to workspace")


class RunPythonArgs(BaseModel):
    """Arguments for run_python tool."""
    code: str = Field(..., description="Python code to execute")


class WebSearchArgs(BaseModel):
    """Arguments for web_search tool."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")


class CalculateArgs(BaseModel):
    """Arguments for calculator tool."""
    expression: str = Field(..., min_length=1, description="Mathematical expression (e.g. '2**10 + sqrt(144)')")


# --- Executors ---

async def read_file_executor(path: str) -> Dict[str, Any]:
    """Read a file from the workspace."""
    logger.info("read_file", path=path)
    try:
        target = _resolve_workspace_path(path)
        if not target.exists():
            return {"error": f"File not found: {path}"}
        if not target.is_file():
            return {"error": f"Not a file: {path}"}
        content = target.read_text(encoding="utf-8")
        return {"path": path, "content": content, "size": len(content)}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Failed to read file: {e}"}


async def write_file_executor(path: str, content: str) -> Dict[str, Any]:
    """Create or overwrite a file in the workspace."""
    logger.info("write_file", path=path, content_length=len(content))
    try:
        target = _resolve_workspace_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": path, "size": len(content), "status": "written"}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Failed to write file: {e}"}


async def list_directory_executor(path: str = ".") -> Dict[str, Any]:
    """List files and directories in the workspace."""
    logger.info("list_directory", path=path)
    try:
        target = _resolve_workspace_path(path)
        if not target.exists():
            return {"error": f"Directory not found: {path}"}
        if not target.is_dir():
            return {"error": f"Not a directory: {path}"}

        entries = []
        for entry in sorted(target.iterdir()):
            info = {"name": entry.name, "type": "dir" if entry.is_dir() else "file"}
            if entry.is_file():
                info["size"] = entry.stat().st_size
            entries.append(info)

        return {"path": path, "entries": entries, "count": len(entries)}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Failed to list directory: {e}"}


async def run_python_executor(code: str) -> Dict[str, Any]:
    """Execute Python code in a subprocess, with workspace as cwd."""
    logger.info("run_python", code_length=len(code))
    workspace = Path(settings.agent_workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=int(settings.tool_timeout_seconds),
            cwd=str(workspace),
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Execution timed out after {settings.tool_timeout_seconds}s"}
    except Exception as e:
        return {"error": f"Failed to run Python code: {e}"}


async def web_search_executor(query: str) -> Dict[str, Any]:
    """Search the web using DuckDuckGo instant answers API (no key needed)."""
    logger.info("web_search", query=query)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        if data.get("AbstractText"):
            results.append({"title": data.get("Heading", ""), "text": data["AbstractText"], "url": data.get("AbstractURL", "")})
        for topic in data.get("RelatedTopics", [])[:5]:
            if "Text" in topic:
                results.append({"text": topic["Text"], "url": topic.get("FirstURL", "")})

        if not results:
            return {"query": query, "results": [], "message": "No instant answer found. Try a more specific query."}

        return {"query": query, "results": results}
    except Exception as e:
        return {"error": f"Web search failed: {e}"}


# Safe math names for calculate
_SAFE_MATH = {name: getattr(math, name) for name in dir(math) if not name.startswith("_")}
_SAFE_MATH["abs"] = abs
_SAFE_MATH["round"] = round
_SAFE_MATH["min"] = min
_SAFE_MATH["max"] = max


async def calculate_executor(expression: str) -> Dict[str, Any]:
    """Safely evaluate a math expression."""
    logger.info("calculate", expression=expression)
    try:
        # Allow only math functions and basic builtins
        result = eval(expression, {"__builtins__": {}}, _SAFE_MATH)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}


# --- Registration ---

def register_default_tools(registry):
    """Register default tools for MVP."""
    from app.tool_proxy.registry import ToolRegistry

    registry.register(
        name="read_file",
        description="Read a file from the agent workspace. Path is relative to workspace root.",
        schema=ReadFileArgs,
        executor=read_file_executor,
        metadata={"category": "filesystem", "safe": True},
    )

    registry.register(
        name="write_file",
        description="Create or overwrite a file in the agent workspace. Creates parent directories automatically.",
        schema=WriteFileArgs,
        executor=write_file_executor,
        metadata={"category": "filesystem", "safe": True},
    )

    registry.register(
        name="list_directory",
        description="List files and directories in the agent workspace.",
        schema=ListDirectoryArgs,
        executor=list_directory_executor,
        metadata={"category": "filesystem", "safe": True},
    )

    registry.register(
        name="run_python",
        description="Execute Python code and return stdout/stderr. Working directory is the agent workspace.",
        schema=RunPythonArgs,
        executor=run_python_executor,
        metadata={"category": "execution", "safe": True},
    )

    registry.register(
        name="web_search",
        description="Search the web using DuckDuckGo. Returns instant answers and related topics.",
        schema=WebSearchArgs,
        executor=web_search_executor,
        metadata={"category": "web", "safe": True},
    )

    registry.register(
        name="calculate",
        description="Evaluate a mathematical expression safely. Supports all math functions (sqrt, sin, cos, log, etc.).",
        schema=CalculateArgs,
        executor=calculate_executor,
        metadata={"category": "utility", "safe": True},
    )

    logger.info("Default tools registered", tools=registry.list_tools())
