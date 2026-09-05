"""Read-only process and CPU scheduling observations."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable

import psutil

from openeuler_mcp.models import (
    ContextSwitchResult,
    ContextSwitchSample,
    CpuTimeRatioResult,
    CpuTimeSample,
    ProcessNode,
    ProcessTreeResult,
)
from openeuler_mcp.timeutils import utc_now_iso

ProgressCallback = Callable[[float, str], Awaitable[None]]


def get_process_tree(
    root_pid: int = 1,
    max_depth: int = 4,
    max_nodes: int = 256,
) -> ProcessTreeResult:
    if root_pid <= 0:
        raise ValueError("root_pid must be greater than zero")
    if not 0 <= max_depth <= 8:
        raise ValueError("max_depth must be between 0 and 8")
    if not 1 <= max_nodes <= 2_000:
        raise ValueError("max_nodes must be between 1 and 2000")

    process_info: dict[int, dict[str, object]] = {}
    try:
        iterator = psutil.process_iter()
        for process in iterator:
            try:
                info = process.as_dict(
                    attrs=["pid", "ppid", "name", "username"],
                    ad_value=None,
                )
            except (psutil.AccessDenied, psutil.NoSuchProcess, PermissionError, OSError):
                continue
            process_info[int(info["pid"])] = info
    except (PermissionError, OSError) as exc:
        raise PermissionError("permission denied while enumerating processes") from exc
    if root_pid not in process_info:
        raise ValueError("root process does not exist or cannot be inspected")

    children: dict[int, list[int]] = defaultdict(list)
    for pid, info in process_info.items():
        if pid != root_pid:
            children[int(info.get("ppid") or 0)].append(pid)
    for values in children.values():
        values.sort()

    returned_nodes = 0
    truncated = False

    def build(pid: int, depth: int) -> ProcessNode:
        nonlocal returned_nodes, truncated
        returned_nodes += 1
        info = process_info[pid]
        nodes: list[ProcessNode] = []
        if depth < max_depth:
            for child_pid in children.get(pid, []):
                if returned_nodes >= max_nodes:
                    truncated = True
                    break
                nodes.append(build(child_pid, depth + 1))
        elif children.get(pid):
            truncated = True
        return ProcessNode(
            pid=pid,
            name=_optional_string(info.get("name")),
            user=_optional_string(info.get("username")),
            children=nodes,
        )

    tree = build(root_pid, 0)
    return ProcessTreeResult(
        summary=(
            f"Process tree root={root_pid}: returned_nodes={returned_nodes}, "
            f"max_depth={max_depth}, truncated={truncated}."
        ),
        captured_at=utc_now_iso(),
        root_pid=root_pid,
        max_depth=max_depth,
        returned_nodes=returned_nodes,
        truncated=truncated,
        tree=tree,
    )


async def monitor_context_switches(
    pid: int | None = None,
    duration_seconds: float = 3.0,
    interval_seconds: float = 1.0,
    progress: ProgressCallback | None = None,
) -> ContextSwitchResult:
    _validate_sampling(duration_seconds, interval_seconds)
    if pid is not None and pid <= 0:
        raise ValueError("pid must be greater than zero")

    if pid is None:
        previous_total = psutil.cpu_stats().ctx_switches
        previous_process: tuple[int, int] | None = None
        process = None
    else:
        try:
            process = psutil.Process(pid)
            counters = process.num_ctx_switches()
        except psutil.NoSuchProcess as exc:
            raise ValueError("process does not exist") from exc
        except psutil.AccessDenied as exc:
            raise PermissionError("permission denied while reading context switches") from exc
        previous_process = (counters.voluntary, counters.involuntary)
        previous_total = 0

    loop = asyncio.get_running_loop()
    started = loop.time()
    samples: list[ContextSwitchSample] = []
    while True:
        elapsed = loop.time() - started
        if elapsed >= duration_seconds:
            break
        await asyncio.sleep(min(interval_seconds, duration_seconds - elapsed))
        if process is None:
            current_total = psutil.cpu_stats().ctx_switches
            total_delta = max(0, current_total - previous_total)
            samples.append(
                ContextSwitchSample(captured_at=utc_now_iso(), total_delta=total_delta)
            )
            previous_total = current_total
        else:
            try:
                counters = process.num_ctx_switches()
            except psutil.NoSuchProcess as exc:
                raise RuntimeError("process exited during context-switch sampling") from exc
            except psutil.AccessDenied as exc:
                raise PermissionError("permission denied during context-switch sampling") from exc
            current = (counters.voluntary, counters.involuntary)
            assert previous_process is not None
            voluntary_delta = max(0, current[0] - previous_process[0])
            involuntary_delta = max(0, current[1] - previous_process[1])
            samples.append(
                ContextSwitchSample(
                    captured_at=utc_now_iso(),
                    voluntary_delta=voluntary_delta,
                    involuntary_delta=involuntary_delta,
                    total_delta=voluntary_delta + involuntary_delta,
                )
            )
            previous_process = current
        if progress is not None:
            elapsed = loop.time() - started
            await progress(min(elapsed / duration_seconds, 1.0), "sampling context switches")

    scope = "system" if pid is None else "process"
    total_delta = sum(sample.total_delta for sample in samples)
    return ContextSwitchResult(
        summary=(
            f"Context switches for {scope}{'' if pid is None else f' pid={pid}'}: "
            f"samples={len(samples)}, total_delta={total_delta}, "
            f"duration={duration_seconds:g}s, interval={interval_seconds:g}s."
        ),
        scope=scope,
        pid=pid,
        duration_seconds=duration_seconds,
        interval_seconds=interval_seconds,
        samples=samples,
    )


async def sample_cpu_time_ratios(
    duration_seconds: float = 3.0,
    interval_seconds: float = 1.0,
    progress: ProgressCallback | None = None,
) -> CpuTimeRatioResult:
    _validate_sampling(duration_seconds, interval_seconds)
    previous = _cpu_times()
    loop = asyncio.get_running_loop()
    started = loop.time()
    samples: list[CpuTimeSample] = []

    while True:
        elapsed = loop.time() - started
        if elapsed >= duration_seconds:
            break
        await asyncio.sleep(min(interval_seconds, duration_seconds - elapsed))
        current = _cpu_times()
        deltas = {name: max(0.0, current[name] - previous.get(name, 0.0)) for name in current}
        total = sum(deltas.values())
        if total > 0:
            samples.append(
                CpuTimeSample(
                    captured_at=utc_now_iso(),
                    ratios={name: value / total for name, value in deltas.items()},
                )
            )
        previous = current
        if progress is not None:
            elapsed = loop.time() - started
            await progress(min(elapsed / duration_seconds, 1.0), "sampling CPU time")

    mean_ratios: dict[str, float] = {}
    if samples:
        states = {name for sample in samples for name in sample.ratios}
        mean_ratios = {
            name: sum(sample.ratios.get(name, 0.0) for sample in samples) / len(samples)
            for name in sorted(states)
        }
    ratio_summary = ", ".join(f"{name}={value:.2%}" for name, value in mean_ratios.items())
    return CpuTimeRatioResult(
        summary=(
            f"CPU time ratios: samples={len(samples)}, duration={duration_seconds:g}s, "
            f"interval={interval_seconds:g}s; mean {ratio_summary or 'unavailable'}."
        ),
        duration_seconds=duration_seconds,
        interval_seconds=interval_seconds,
        samples=samples,
    )


def _cpu_times() -> dict[str, float]:
    values = psutil.cpu_times()._asdict()
    # Linux guest values are already included in user/nice and must not be counted twice.
    return {
        name: float(value)
        for name, value in values.items()
        if name not in {"guest", "guest_nice"}
    }


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _validate_sampling(duration_seconds: float, interval_seconds: float) -> None:
    if not 0.1 <= duration_seconds <= 30:
        raise ValueError("duration_seconds must be between 0.1 and 30")
    if not 0.1 <= interval_seconds <= 5:
        raise ValueError("interval_seconds must be between 0.1 and 5")
    if interval_seconds > duration_seconds:
        raise ValueError("interval_seconds must not exceed duration_seconds")
