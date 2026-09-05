import pytest
from pydantic import ValidationError

from openeuler_mcp.algorithms.scheduling import simulate_cpu_scheduling
from openeuler_mcp.models import CpuJobInput


def test_round_robin_uses_cumulative_waiting_time() -> None:
    result = simulate_cpu_scheduling(
        [CpuJobInput(pid="A", burst=4), CpuJobInput(pid="B", burst=2)],
        "RR",
        1,
    )

    by_pid = {item.pid: item for item in result.jobs}
    assert by_pid["A"].waiting == pytest.approx(2)
    assert by_pid["B"].waiting == pytest.approx(2)
    assert by_pid["A"].response == pytest.approx(0)
    assert by_pid["B"].response == pytest.approx(1)
    assert result.metrics.average_waiting == pytest.approx(2)
    assert "RR scheduling for 2 jobs" in result.summary


@pytest.mark.parametrize("algorithm", ["FCFS", "SJF", "PRIORITY", "RR"])
def test_all_schedulers_produce_complete_metrics(algorithm: str) -> None:
    jobs = [
        CpuJobInput(pid="A", arrival=0, burst=3, priority=2),
        CpuJobInput(pid="B", arrival=1, burst=1, priority=1),
    ]
    result = simulate_cpu_scheduling(jobs, algorithm, 1)

    assert {item.pid for item in result.jobs} == {"A", "B"}
    assert sum(item.duration for item in result.timeline) == pytest.approx(4)
    assert all(item.waiting >= 0 for item in result.jobs)


def test_scheduler_rejects_non_positive_time_slice_and_duplicate_pid() -> None:
    jobs = [CpuJobInput(pid="A", burst=1)]
    with pytest.raises(ValueError, match="time_slice"):
        simulate_cpu_scheduling(jobs, "RR", 0)
    with pytest.raises(ValueError, match="unique"):
        simulate_cpu_scheduling(jobs + jobs, "FCFS")


def test_job_model_rejects_non_positive_burst() -> None:
    with pytest.raises(ValidationError):
        CpuJobInput(pid="A", burst=0)
