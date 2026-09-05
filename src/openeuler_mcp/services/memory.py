"""Read-only memory data collection."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

import psutil

from openeuler_mcp.models import (
    MemoryInfoResult,
    MemoryMapping,
    MemoryStats,
    MemoryTrendResult,
    MemoryTrendSample,
    ProcessMemoryResult,
    SwapStats,
)
from openeuler_mcp.timeutils import utc_now_iso

ProgressCallback = Callable[[float, str], Awaitable[None]]


def get_memory_info() -> MemoryInfoResult:
    vm = psutil.virtual_memory()
    try:
        raw_swap = psutil.swap_memory()
        swap = SwapStats(
            total_bytes=raw_swap.total,
            used_bytes=raw_swap.used,
            free_bytes=raw_swap.free,
            percent=raw_swap.percent,
            swapped_in_bytes=raw_swap.sin,
            swapped_out_bytes=raw_swap.sout,
        )
    except (PermissionError, OSError):
        swap = None
    proc_meminfo = _read_proc_meminfo()
    source = _memory_source(proc_meminfo is not None, swap is not None)
    swap_summary = (
        f"used={swap.used_bytes} total={swap.total_bytes} bytes"
        if swap is not None
        else "unavailable"
    )
    return MemoryInfoResult(
        summary=(
            f"RAM used={vm.used} available={vm.available} total={vm.total} bytes "
            f"({vm.percent}%); swap {swap_summary}; source={source}."
        ),
        captured_at=utc_now_iso(),
        memory=MemoryStats(
            total_bytes=vm.total,
            available_bytes=vm.available,
            used_bytes=vm.used,
            free_bytes=vm.free,
            cached_bytes=getattr(vm, "cached", None),
            buffers_bytes=getattr(vm, "buffers", None),
            percent=vm.percent,
        ),
        swap=swap,
        proc_meminfo=proc_meminfo,
        source=source,
    )


def get_process_memory(pid: int, mapping_limit: int = 20) -> ProcessMemoryResult:
    if pid <= 0:
        raise ValueError("pid must be greater than zero")
    if not 1 <= mapping_limit <= 200:
        raise ValueError("mapping_limit must be between 1 and 200")
    try:
        process = psutil.Process(pid)
        with process.oneshot():
            name = process.name()
            info = process.memory_info()
        try:
            raw_maps = process.memory_maps(grouped=True)
            source = "psutil.memory_maps"
        except (AttributeError, NotImplementedError):
            raw_maps = []
            source = "psutil.memory_info (memory maps unavailable)"
    except psutil.NoSuchProcess as exc:
        raise ValueError("process does not exist") from exc
    except psutil.AccessDenied as exc:
        raise PermissionError("permission denied while reading process memory") from exc
    except psutil.ZombieProcess as exc:
        raise RuntimeError("process became a zombie while reading memory") from exc
    except OSError as exc:
        raise RuntimeError("unable to read process memory information") from exc

    mappings = [
        MemoryMapping(
            path=item.path or "<anonymous>",
            rss_bytes=item.rss,
            size_bytes=getattr(item, "size", 0),
            private_bytes=_memory_component(item, "private", "private_clean", "private_dirty"),
            shared_bytes=_memory_component(item, "shared", "shared_clean", "shared_dirty"),
        )
        for item in raw_maps
    ]
    mappings.sort(key=lambda item: item.rss_bytes, reverse=True)
    returned_mappings = min(len(mappings), mapping_limit)
    return ProcessMemoryResult(
        summary=(
            f"Process {pid} ({name}): RSS={info.rss} bytes, VMS={info.vms} bytes; "
            f"mappings returned={returned_mappings}/{len(mappings)}; source={source}."
        ),
        captured_at=utc_now_iso(),
        pid=pid,
        name=name,
        rss_bytes=info.rss,
        vms_bytes=info.vms,
        mappings=mappings[:mapping_limit],
        returned_mappings=returned_mappings,
        total_mappings=len(mappings),
        source=source,
    )


async def sample_memory_trend(
    duration_seconds: float = 3.0,
    interval_seconds: float = 1.0,
    progress: ProgressCallback | None = None,
) -> MemoryTrendResult:
    _validate_sampling(duration_seconds, interval_seconds)
    loop = asyncio.get_running_loop()
    started = loop.time()
    samples: list[MemoryTrendSample] = []

    while True:
        vm = psutil.virtual_memory()
        samples.append(
            MemoryTrendSample(
                captured_at=utc_now_iso(),
                used_bytes=vm.used,
                available_bytes=vm.available,
                percent=vm.percent,
            )
        )
        elapsed = loop.time() - started
        if elapsed >= duration_seconds:
            break
        if progress is not None:
            await progress(min(elapsed / duration_seconds, 1.0), "sampling memory")
        await asyncio.sleep(min(interval_seconds, duration_seconds - elapsed))

    initial_used_bytes = max(samples[0].used_bytes, 1)
    change_ratio = (samples[-1].used_bytes - samples[0].used_bytes) / initial_used_bytes
    if change_ratio > 0.05:
        trend = "increasing"
    elif change_ratio < -0.05:
        trend = "decreasing"
    else:
        trend = "stable"
    return MemoryTrendResult(
        summary=(
            f"Memory trend={trend}; change_ratio={change_ratio:.6f}; "
            f"samples={len(samples)} over {duration_seconds:g}s at {interval_seconds:g}s intervals."
        ),
        trend=trend,
        change_ratio=change_ratio,
        samples=samples,
        duration_seconds=duration_seconds,
        interval_seconds=interval_seconds,
    )


def _read_proc_meminfo() -> dict[str, str] | None:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return None
    result: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition(":")
            if separator:
                result[key.strip()] = value.strip()
    except (OSError, PermissionError):
        return None
    return result


def _memory_source(has_proc: bool, has_swap: bool) -> str:
    sources = ["psutil"]
    if has_proc:
        sources.append("/proc/meminfo")
    if not has_swap:
        sources.append("swap unavailable")
    return " + ".join(sources)


def _memory_component(
    item: object,
    aggregate_name: str,
    *component_names: str,
) -> int | None:
    aggregate = getattr(item, aggregate_name, None)
    if aggregate is not None:
        return int(aggregate)
    values = [getattr(item, name, None) for name in component_names]
    available = [int(value) for value in values if value is not None]
    return sum(available) if available else None


def _validate_sampling(duration_seconds: float, interval_seconds: float) -> None:
    if not 0.1 <= duration_seconds <= 30:
        raise ValueError("duration_seconds must be between 0.1 and 30")
    if not 0.1 <= interval_seconds <= 5:
        raise ValueError("interval_seconds must be between 0.1 and 5")
    if interval_seconds > duration_seconds:
        raise ValueError("interval_seconds must not exceed duration_seconds")
