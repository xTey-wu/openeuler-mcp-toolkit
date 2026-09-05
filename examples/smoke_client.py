"""List tools and invoke one simulation through the official MCP client."""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "openeuler_mcp"],
        env=dict(os.environ),
    )
    async with (
        stdio_client(parameters) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        print("Tools:", ", ".join(tool.name for tool in tools.tools))
        result = await session.call_tool(
            "simulate_cpu_scheduling",
            {
                "jobs": [
                    {"pid": "A", "arrival": 0, "burst": 4, "priority": 2},
                    {"pid": "B", "arrival": 0, "burst": 2, "priority": 1},
                ],
                "algorithm": "RR",
                "time_slice": 1,
            },
        )
        print(result.structuredContent)


if __name__ == "__main__":
    asyncio.run(run())
