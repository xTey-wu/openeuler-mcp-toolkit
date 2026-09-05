"""MCP registrations for process and scheduling tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field

from openeuler_mcp.algorithms import simulate_cpu_scheduling as run_cpu_scheduling
from openeuler_mcp.models import (
    ContextSwitchResult,
    CpuJobInput,
    CpuSchedulingResult,
    CpuTimeRatioResult,
    ProcessTreeResult,
)
from openeuler_mcp.services.scheduler import (
    get_process_tree as collect_process_tree,
)
from openeuler_mcp.services.scheduler import (
    monitor_context_switches as collect_context_switches,
)
from openeuler_mcp.services.scheduler import (
    sample_cpu_time_ratios as collect_cpu_time_ratios,
)
from openeuler_mcp.tools.annotations import OBSERVATION_ANNOTATIONS, SIMULATION_ANNOTATIONS


def register_scheduler_tools(mcp: FastMCP) -> None:
    @mcp.tool(annotations=OBSERVATION_ANNOTATIONS)
    def get_process_tree(
        root_pid: Annotated[
            int,
            Field(gt=0, description="Root PID for the returned parent-child tree; default 1"),
        ] = 1,
        max_depth: Annotated[
            int,
            Field(
                ge=0,
                le=8,
                description=(
                    "Maximum child depth; root is depth 0; default 4. "
                    "Pass an explicitly requested depth even when it is below the default."
                ),
            ),
        ] = 4,
        max_nodes: Annotated[
            int,
            Field(ge=1, le=2_000, description="Hard cap on returned process nodes; default 256"),
        ] = 256,
    ) -> ProcessTreeResult:
        """READ-ONLY PROCESS TREE starting at root_pid.

        The result is bounded by depth and node count. This cannot stop, kill,
        reprioritize, or otherwise modify any process.
        """

        return collect_process_tree(root_pid, max_depth, max_nodes)

    @mcp.tool(annotations=OBSERVATION_ANNOTATIONS)
    async def monitor_context_switches(
        ctx: Context,
        pid: Annotated[
            int | None,
            Field(gt=0, description="PID for per-process sampling; null means system-wide"),
        ] = None,
        duration_seconds: Annotated[
            float,
            Field(ge=0.1, le=30, description="Total sampling duration in seconds"),
        ] = 3.0,
        interval_seconds: Annotated[
            float,
            Field(ge=0.1, le=5, description="Seconds between context-switch samples"),
        ] = 1.0,
    ) -> ContextSwitchResult:
        """READ-ONLY CONTEXT-SWITCH sampling for the system or one PID.

        This observes counters only and cannot stop or modify processes. It is not a
        CPU scheduling simulation.
        """

        async def progress(value: float, message: str) -> None:
            await ctx.report_progress(value, total=1.0, message=message)

        return await collect_context_switches(pid, duration_seconds, interval_seconds, progress)

    @mcp.tool(annotations=SIMULATION_ANNOTATIONS)
    def simulate_cpu_scheduling(
        jobs: Annotated[
            list[CpuJobInput],
            Field(
                min_length=1,
                max_length=10_000,
                description="Required complete list of every simulated job; do not omit jobs",
            ),
        ],
        algorithm: Annotated[
            str,
            Field(
                description=(
                    "Required scheduling algorithm: FCFS, SJF, RR, or PRIORITY; "
                    "lower priority numbers run first"
                )
            ),
        ],
        time_slice: Annotated[
            float,
            Field(gt=0, description="RR quantum; ignored for non-RR algorithms; default 1"),
        ] = 1.0,
    ) -> CpuSchedulingResult:
        """CALL THIS EXACT TOOL for RR, SJF, FCFS, or PRIORITY job scheduling.

        This is a pure simulation. Include every requested job, the explicit algorithm,
        and RR time slice. The tool name must remain simulate_cpu_scheduling. This does
        not inspect, stop, or modify real processes.
        """

        return run_cpu_scheduling(jobs, algorithm, time_slice)

    @mcp.tool(annotations=OBSERVATION_ANNOTATIONS)
    async def sample_cpu_time_ratios(
        ctx: Context,
        duration_seconds: Annotated[
            float,
            Field(ge=0.1, le=30, description="Total CPU sampling duration in seconds"),
        ] = 3.0,
        interval_seconds: Annotated[
            float,
            Field(ge=0.1, le=5, description="Seconds between CPU-time samples"),
        ] = 1.0,
    ) -> CpuTimeRatioResult:
        """READ-ONLY sampling of live CPU user/system/idle percentages.

        Never use for job lists, algorithms, RR, SJF, Priority, or time slices. This is
        not context-switch monitoring, process control, or CPU scheduling simulation.
        """

        async def progress(value: float, message: str) -> None:
            await ctx.report_progress(value, total=1.0, message=message)

        return await collect_cpu_time_ratios(duration_seconds, interval_seconds, progress)


__all__ = ["register_scheduler_tools"]
