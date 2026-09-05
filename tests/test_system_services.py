import asyncio
import os
from pathlib import Path

import psutil
import pytest

from openeuler_mcp.services.filesystem import monitor_file_metadata
from openeuler_mcp.services.memory import get_memory_info, get_process_memory, sample_memory_trend
from openeuler_mcp.services.scheduler import get_process_tree, sample_cpu_time_ratios


def test_current_memory_and_process_are_readable() -> None:
    memory = get_memory_info()
    assert memory.memory.total_bytes > 0
    assert "RAM used=" in memory.summary

    try:
        process = get_process_memory(os.getpid(), mapping_limit=5)
    except (PermissionError, RuntimeError):
        pytest.skip("sandbox does not permit process memory inspection")
    assert process.pid == os.getpid()
    assert process.returned_mappings <= 5
    assert f"Process {os.getpid()}" in process.summary


def test_process_tree_can_start_at_current_process() -> None:
    try:
        result = get_process_tree(os.getpid(), max_depth=0)
    except PermissionError:
        pytest.skip("sandbox does not permit process enumeration")

    assert result.tree.pid == os.getpid()
    assert result.returned_nodes == 1
    assert "returned_nodes=1" in result.summary


def test_process_tree_skips_inaccessible_unrelated_processes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InaccessibleProcess:
        def as_dict(self, **_kwargs: object) -> dict[str, object]:
            raise psutil.AccessDenied(pid=999)

    class VisibleProcess:
        def as_dict(self, **_kwargs: object) -> dict[str, object]:
            return {"pid": 42, "ppid": 1, "name": "visible", "username": "tester"}

    monkeypatch.setattr(
        "openeuler_mcp.services.scheduler.psutil.process_iter",
        lambda: iter([InaccessibleProcess(), VisibleProcess()]),
    )

    result = get_process_tree(42, max_depth=0)

    assert result.tree.pid == 42
    assert result.tree.name == "visible"
    assert result.returned_nodes == 1


def test_sampling_validates_duration() -> None:
    with pytest.raises(ValueError, match="duration_seconds"):
        asyncio.run(sample_memory_trend(0, 0.1))
    with pytest.raises(ValueError, match="interval_seconds"):
        asyncio.run(sample_cpu_time_ratios(1, 2))


def test_file_monitor_reports_initial_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "watched.txt"
    target.write_text("hello", encoding="utf-8")
    monkeypatch.setenv("OPENEULER_MCP_ALLOWED_ROOTS", str(tmp_path))

    result = asyncio.run(monitor_file_metadata(str(target), 0.1, 0.1))

    assert result.method == "metadata_polling"
    assert result.events[0].event == "initial"
    assert "changes=0" in result.summary
