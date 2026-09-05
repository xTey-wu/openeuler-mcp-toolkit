from mcp.server.fastmcp import FastMCP

from .filesystem import register_filesystem_tools
from .memory import register_memory_tools
from .scheduler import register_scheduler_tools


def register_tools(mcp: FastMCP) -> None:
    register_memory_tools(mcp)
    register_filesystem_tools(mcp)
    register_scheduler_tools(mcp)


__all__ = ["register_tools"]
