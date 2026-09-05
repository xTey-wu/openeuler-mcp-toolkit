"""CPU scheduling simulations with verifiable metrics."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from openeuler_mcp.models import (
    CpuJobInput,
    CpuSchedulingResult,
    JobScheduleMetrics,
    ScheduleMetrics,
    ScheduleSlice,
)

SUPPORTED_ALGORITHMS = {"FCFS", "SJF", "RR", "PRIORITY"}


@dataclass
class _JobState:
    pid: str
    arrival: float
    burst: float
    priority: int
    remaining: float
    first_start: float | None = None
    completion: float | None = None

    @classmethod
    def from_input(cls, job: CpuJobInput) -> _JobState:
        return cls(job.pid, job.arrival, job.burst, job.priority, job.burst)


def simulate_cpu_scheduling(
    jobs: list[CpuJobInput],
    algorithm: str = "RR",
    time_slice: float = 1.0,
) -> CpuSchedulingResult:
    if not jobs:
        raise ValueError("jobs must not be empty")
    if len(jobs) > 10_000:
        raise ValueError("jobs must not contain more than 10000 entries")
    algorithm = algorithm.upper()
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(f"unsupported scheduling algorithm: {algorithm}")
    if algorithm == "RR" and time_slice <= 0:
        raise ValueError("time_slice must be greater than zero for RR")

    pids = [job.pid for job in jobs]
    if len(pids) != len(set(pids)):
        raise ValueError("job pid values must be unique")

    waiting = sorted((_JobState.from_input(job) for job in jobs), key=lambda item: item.arrival)
    ready: deque[_JobState] = deque()
    timeline: list[ScheduleSlice] = []
    clock = 0.0

    def enqueue_ready() -> None:
        while waiting and waiting[0].arrival <= clock:
            ready.append(waiting.pop(0))

    enqueue_ready()
    while ready or waiting:
        if not ready:
            clock = waiting[0].arrival
            enqueue_ready()

        if algorithm == "FCFS":
            job = ready.popleft()
        elif algorithm == "SJF":
            job = min(ready, key=lambda item: (item.remaining, item.arrival, item.pid))
            ready.remove(job)
        elif algorithm == "PRIORITY":
            job = min(ready, key=lambda item: (item.priority, item.arrival, item.pid))
            ready.remove(job)
        else:
            job = ready.popleft()

        start = clock
        if job.first_start is None:
            job.first_start = start
        run = min(time_slice, job.remaining) if algorithm == "RR" else job.remaining
        clock += run
        job.remaining -= run
        timeline.append(
            ScheduleSlice(
                pid=job.pid,
                start=start,
                finish=clock,
                duration=run,
                priority=job.priority if algorithm == "PRIORITY" else None,
            )
        )

        enqueue_ready()
        if job.remaining > 1e-12:
            ready.append(job)
        else:
            job.remaining = 0
            job.completion = clock
        enqueue_ready()

    # Completed jobs are no longer in queues, so rebuild their immutable inputs and derive
    # completion/response from the timeline.
    metrics_by_pid: list[JobScheduleMetrics] = []
    for original in jobs:
        slices = [item for item in timeline if item.pid == original.pid]
        completion = slices[-1].finish
        response = slices[0].start - original.arrival
        turnaround = completion - original.arrival
        metrics_by_pid.append(
            JobScheduleMetrics(
                pid=original.pid,
                completion=completion,
                turnaround=turnaround,
                waiting=turnaround - original.burst,
                response=response,
            )
        )

    count = len(metrics_by_pid)
    summary = ScheduleMetrics(
        average_waiting=sum(item.waiting for item in metrics_by_pid) / count,
        average_turnaround=sum(item.turnaround for item in metrics_by_pid) / count,
        average_response=sum(item.response for item in metrics_by_pid) / count,
    )
    return CpuSchedulingResult(
        summary=(
            f"{algorithm} scheduling for {count} jobs: "
            f"average_waiting={summary.average_waiting:g}, "
            f"average_turnaround={summary.average_turnaround:g}, "
            f"average_response={summary.average_response:g}."
        ),
        algorithm=algorithm,
        time_slice=time_slice if algorithm == "RR" else None,
        timeline=timeline,
        jobs=metrics_by_pid,
        metrics=summary,
    )
