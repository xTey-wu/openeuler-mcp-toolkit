"""MCP server factory and console entry point."""

from mcp.server.fastmcp import FastMCP

from openeuler_mcp.tools import register_tools
from openeuler_mcp.tools.strict_arguments import enforce_strict_tool_arguments

SERVER_INSTRUCTIONS = """
This server is strictly read-only. It has no file deletion, file modification, process
termination, process control, or privilege-changing capability. Refuse requests to delete,
modify, kill, terminate, or stop anything; do not substitute an unrelated read-only tool.

Choose at most one tool and send only fields defined by that tool's input schema. Distinguish
live observations from pure simulations: page reference strings with FIFO/LRU/CLOCK/OPT use
simulate_page_replacement; simulated disk files and blocks use simulate_disk_allocation;
directories and max_files use analyze_file_distribution; job lists with FCFS/SJF/RR/PRIORITY
use simulate_cpu_scheduling. Preserve every user-specified item and explicit algorithm. Always
send every numeric limit, duration, interval, depth, count, and size stated by the user, even
when the matching schema field is optional or has a default.

File tools are limited to OPENEULER_MCP_ALLOWED_ROOTS. Metadata polling reports only size and
timestamp changes. Always base the final response on the structured result, especially its
summary field, and report tool errors instead of claiming completion.
""".strip()


def create_server() -> FastMCP:
    server = FastMCP(name="openEuler MCP Toolkit", instructions=SERVER_INSTRUCTIONS)
    register_tools(server)
    enforce_strict_tool_arguments(server)
    return server


mcp = create_server()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
