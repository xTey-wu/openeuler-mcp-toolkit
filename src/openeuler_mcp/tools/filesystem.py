"""MCP registrations for filesystem tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from openeuler_mcp.algorithms import simulate_disk_allocation as run_disk_allocation
from openeuler_mcp.models import (
    DiskAllocationResult,
    DiskFileInput,
    DiskScenario,
    FileDistributionResult,
    FileMetadataResult,
    FilesystemInfoResult,
)
from openeuler_mcp.services.filesystem import (
    analyze_file_distribution as collect_file_distribution,
)
from openeuler_mcp.services.filesystem import (
    get_filesystem_info as collect_filesystem_info,
)
from openeuler_mcp.services.filesystem import (
    monitor_file_metadata as collect_file_metadata,
)
from openeuler_mcp.tools.annotations import OBSERVATION_ANNOTATIONS, SIMULATION_ANNOTATIONS


def register_filesystem_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations=OBSERVATION_ANNOTATIONS)
    def get_filesystem_info() -> FilesystemInfoResult:
        """READ-ONLY mounted-filesystem snapshot.

        Returns space and inode usage. Takes no arguments and never scans, changes,
        or deletes files.
        """

        return collect_filesystem_info()

    @mcp.tool(annotations=OBSERVATION_ANNOTATIONS)
    def analyze_file_distribution(
        path: Annotated[
            str,
            Field(min_length=1, description="Directory to scan inside allowed roots"),
        ] = ".",
        max_depth: Annotated[
            int,
            Field(ge=0, le=8, description="Maximum directory depth to scan; default 3"),
        ] = 3,
        top_n: Annotated[
            int,
            Field(ge=1, le=50, description="Number of largest files/directories; default 5"),
        ] = 5,
        max_files: Annotated[
            int,
            Field(ge=1, le=100_000, description="Hard cap on files examined; default 100000"),
        ] = 100_000,
    ) -> FileDistributionResult:
        """READ-ONLY DIRECTORY SCAN for counts, extensions, sizes, and largest paths.

        Use max_files to cap scanning. Not a disk-allocation simulation and cannot
        delete files.
        """

        return collect_file_distribution(path, max_depth, top_n, max_files)

    @mcp.tool(annotations=OBSERVATION_ANNOTATIONS)
    async def monitor_file_metadata(
        path: Annotated[
            str,
            Field(min_length=1, description="Required file path inside allowed roots"),
        ],
        ctx: Context,
        duration_seconds: Annotated[
            float,
            Field(ge=0.1, le=30, description="Total monitoring duration in seconds"),
        ] = 5.0,
        interval_seconds: Annotated[
            float,
            Field(ge=0.1, le=5, description="Seconds between metadata polls"),
        ] = 1.0,
    ) -> FileMetadataResult:
        """READ-ONLY polling of one FILE's size and timestamps.

        Requires the exact file path. This is not a directory scan, access tracing,
        or a delete/modify operation.
        """

        async def progress(value: float, message: str) -> None:
            await ctx.report_progress(value, total=1.0, message=message)

        return await collect_file_metadata(path, duration_seconds, interval_seconds, progress)

    @mcp.tool(annotations=SIMULATION_ANNOTATIONS)
    def simulate_disk_allocation(
        files: Annotated[
            list[DiskFileInput],
            Field(
                min_length=1,
                max_length=256,
                description='Required simulated files, e.g. [{"name":"A","size_bytes":9000}]',
            ),
        ],
        strategy: Annotated[
            str,
            Field(description="Required disk allocation strategy: contiguous, linked, or indexed"),
        ],
        total_blocks: Annotated[
            int,
            Field(ge=1, le=100_000, description="Total simulated disk blocks; default 128"),
        ] = 128,
        block_size_bytes: Annotated[
            int,
            Field(gt=0, le=1024 * 1024 * 1024, description="Bytes per block; default 4096"),
        ] = 4096,
    ) -> DiskAllocationResult:
        """PURE DISK-BLOCK ALLOCATION SIMULATION using flat arguments.

        Arguments are files, strategy, total_blocks, and block_size_bytes. Not for
        page-reference algorithms, directory scans, or real disk changes.
        """

        scenario = DiskScenario(files=files, total_blocks=total_blocks)
        return run_disk_allocation(scenario, strategy, block_size_bytes)


__all__ = ["register_filesystem_tools"]
