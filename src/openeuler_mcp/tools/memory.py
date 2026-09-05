"""MCP registrations for memory tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from openeuler_mcp.algorithms import simulate_page_replacement as run_page_replacement
from openeuler_mcp.models import (
    MemoryInfoResult,
    MemoryTrendResult,
    PageReplacementResult,
    ProcessMemoryResult,
)
from openeuler_mcp.services.memory import (
    get_memory_info as collect_memory_info,
)
from openeuler_mcp.services.memory import (
    get_process_memory as collect_process_memory,
)
from openeuler_mcp.services.memory import (
    sample_memory_trend as collect_memory_trend,
)
from openeuler_mcp.tools.annotations import OBSERVATION_ANNOTATIONS, SIMULATION_ANNOTATIONS


def register_memory_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations=OBSERVATION_ANNOTATIONS)
    def get_memory_info() -> MemoryInfoResult:
        """READ-ONLY memory snapshot.

        Use only for current system RAM, swap, and /proc/meminfo. Takes no arguments.
        Never deletes files or stops processes.
        """

        return collect_memory_info()

    @mcp.tool(annotations=OBSERVATION_ANNOTATIONS)
    def get_process_memory(
        pid: Annotated[
            int,
            Field(gt=0, description="Required operating-system PID from the user request"),
        ],
        mapping_limit: Annotated[
            int,
            Field(
                ge=1,
                le=200,
                description=(
                    "Maximum memory mappings returned, sorted by RSS; default 20. "
                    "If the user requests top N mappings, pass N here explicitly."
                ),
            ),
        ] = 20,
    ) -> ProcessMemoryResult:
        """READ-ONLY memory inspection for one PID.

        Returns RSS, VMS, and largest mappings. This cannot stop, kill, or modify the
        process; refuse such requests.
        """

        return collect_process_memory(pid, mapping_limit)

    @mcp.tool(annotations=OBSERVATION_ANNOTATIONS)
    async def sample_memory_trend(
        ctx: Context,
        duration_seconds: Annotated[
            float,
            Field(ge=0.1, le=30, description="Total sampling duration in seconds"),
        ] = 3.0,
        interval_seconds: Annotated[
            float,
            Field(ge=0.1, le=5, description="Seconds between memory samples"),
        ] = 1.0,
    ) -> MemoryTrendResult:
        """READ-ONLY time-series sampling of system memory.

        Use for trends over a requested duration, not for a single snapshot, files,
        page algorithms, or processes.
        """

        async def progress(value: float, message: str) -> None:
            await ctx.report_progress(value, total=1.0, message=message)

        return await collect_memory_trend(duration_seconds, interval_seconds, progress)

    @mcp.tool(annotations=SIMULATION_ANNOTATIONS)
    def simulate_page_replacement(
        reference_string: Annotated[
            list[int],
            Field(
                min_length=1,
                max_length=100_000,
                description="Required ordered page-reference sequence, for example [1,2,3,1,4]",
            ),
        ],
        algorithm: Annotated[
            str,
            Field(description="Required page algorithm: FIFO, LRU, CLOCK, or OPT"),
        ],
        frame_count: Annotated[
            int,
            Field(ge=1, le=10_000, description="Number of simulated page frames; default 4"),
        ] = 4,
    ) -> PageReplacementResult:
        """PURE PAGE-REPLACEMENT SIMULATION using FIFO/LRU/CLOCK/OPT.

        Use only for a page reference string. Not for disk block allocation, filesystem
        scans, or live memory. Required JSON keys: reference_string and algorithm.
        """

        return run_page_replacement(reference_string, frame_count, algorithm)


__all__ = ["register_memory_tools"]
