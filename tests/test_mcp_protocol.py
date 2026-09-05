import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "get_memory_info",
    "get_process_memory",
    "sample_memory_trend",
    "simulate_page_replacement",
    "get_filesystem_info",
    "analyze_file_distribution",
    "monitor_file_metadata",
    "simulate_disk_allocation",
    "get_process_tree",
    "monitor_context_switches",
    "simulate_cpu_scheduling",
    "sample_cpu_time_ratios",
}


@pytest.mark.integration
def test_stdio_server_lists_and_calls_structured_tools(tmp_path: Path) -> None:
    async def run() -> None:
        environment = dict(os.environ)
        environment["OPENEULER_MCP_ALLOWED_ROOTS"] = str(tmp_path)
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "openeuler_mcp"],
            env=environment,
        )
        async with (
            stdio_client(parameters) as (reader, writer),
            ClientSession(reader, writer) as session,
        ):
            await session.initialize()
            listed = await session.list_tools()
            assert {tool.name for tool in listed.tools} == EXPECTED_TOOLS
            assert all(tool.outputSchema is not None for tool in listed.tools)
            assert all(
                tool.inputSchema.get("additionalProperties") is False for tool in listed.tools
            )
            assert all(tool.annotations is not None for tool in listed.tools)
            assert all(tool.annotations.readOnlyHint is True for tool in listed.tools)
            assert all(tool.annotations.destructiveHint is False for tool in listed.tools)

            by_name = {tool.name: tool for tool in listed.tools}
            page_schema = by_name["simulate_page_replacement"].inputSchema
            assert "algorithm" in page_schema["required"]
            scheduling_schema = by_name["simulate_cpu_scheduling"].inputSchema
            assert "algorithm" in scheduling_schema["required"]
            disk_schema = by_name["simulate_disk_allocation"].inputSchema
            assert "files" in disk_schema["properties"]
            assert "total_blocks" in disk_schema["properties"]
            assert "scenario" not in disk_schema["properties"]

            result = await session.call_tool(
                "simulate_page_replacement",
                {"reference_string": [1, 2, 1], "frame_count": 2, "algorithm": "LRU"},
            )
            assert result.isError is False
            assert result.structuredContent is not None
            assert result.structuredContent["hits"] == 1
            assert "faults=2/3" in result.structuredContent["summary"]

            disk_result = await session.call_tool(
                "simulate_disk_allocation",
                {
                    "files": [{"name": "A", "size_bytes": 8192}],
                    "strategy": "indexed",
                    "total_blocks": 8,
                    "block_size_bytes": 4096,
                },
            )
            assert disk_result.isError is False
            assert disk_result.structuredContent is not None
            assert disk_result.structuredContent["allocations"][0]["index_block"] == 0

            invalid = await session.call_tool(
                "simulate_page_replacement",
                {"reference_string": [1], "frame_count": 1, "algorithm": "UNKNOWN"},
            )
            assert invalid.isError is True

            extra_argument = await session.call_tool(
                "get_memory_info",
                {"title": "get_memory_infoArguments"},
            )
            assert extra_argument.isError is True

    asyncio.run(run())
