"""Read-only filesystem inspection with explicit path boundaries."""

from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import psutil

from openeuler_mcp.config import display_path, resolve_allowed_path
from openeuler_mcp.models import (
    ExtensionStats,
    FileDistributionResult,
    FileMetadata,
    FileMetadataEvent,
    FileMetadataResult,
    FilesystemInfoResult,
    InodeStats,
    PartitionInfo,
    RankedPath,
)
from openeuler_mcp.timeutils import utc_now_iso

ProgressCallback = Callable[[float, str], Awaitable[None]]


def get_filesystem_info() -> FilesystemInfoResult:
    partitions: list[PartitionInfo] = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        partitions.append(
            PartitionInfo(
                device=part.device,
                mountpoint=part.mountpoint,
                filesystem_type=part.fstype,
                total_bytes=usage.total,
                used_bytes=usage.used,
                free_bytes=usage.free,
                percent=usage.percent,
                inodes=_inode_info(Path(part.mountpoint)),
            )
        )
    return FilesystemInfoResult(
        summary=(
            f"Found {len(partitions)} mounted filesystems with space usage; "
            "inode data is included when available."
        ),
        captured_at=utc_now_iso(),
        partitions=partitions,
    )


def analyze_file_distribution(
    path: str = ".",
    max_depth: int = 3,
    top_n: int = 5,
    max_files: int = 100_000,
) -> FileDistributionResult:
    if not 0 <= max_depth <= 8:
        raise ValueError("max_depth must be between 0 and 8")
    if not 1 <= top_n <= 50:
        raise ValueError("top_n must be between 1 and 50")
    if not 1 <= max_files <= 100_000:
        raise ValueError("max_files must be between 1 and 100000")
    root = resolve_allowed_path(path)
    if not root.is_dir():
        raise ValueError("path must refer to a directory")

    size_by_extension: dict[str, int] = defaultdict(int)
    count_by_extension: dict[str, int] = defaultdict(int)
    files: list[tuple[str, int]] = []
    directory_sizes: dict[str, int] = defaultdict(int)
    truncated = False

    for current_root, directories, names in os.walk(root, followlinks=False):
        current = Path(current_root)
        depth = len(current.relative_to(root).parts)
        directories[:] = [
            name for name in directories if not (current / name).is_symlink()
        ]
        if depth >= max_depth:
            directories[:] = []
        for name in names:
            candidate = current / name
            if candidate.is_symlink():
                continue
            try:
                stat = candidate.stat(follow_symlinks=False)
            except (PermissionError, FileNotFoundError, OSError):
                continue
            relative = str(candidate.relative_to(root))
            extension = candidate.suffix.lower() or "<no_ext>"
            size_by_extension[extension] += stat.st_size
            count_by_extension[extension] += 1
            files.append((relative, stat.st_size))
            parent = candidate.parent
            while True:
                directory_sizes[str(parent.relative_to(root)) or "."] += stat.st_size
                if parent == root:
                    break
                parent = parent.parent
            if len(files) >= max_files:
                truncated = True
                break
        if truncated:
            break

    extension_rows = [
        ExtensionStats(
            extension=extension,
            file_count=count_by_extension[extension],
            total_bytes=size,
        )
        for extension, size in size_by_extension.items()
    ]
    extension_rows.sort(key=lambda item: (-item.total_bytes, item.extension))
    files.sort(key=lambda item: (-item[1], item[0]))
    ranked_directories = sorted(directory_sizes.items(), key=lambda item: (-item[1], item[0]))
    largest_file = f"{files[0][0]} ({files[0][1]} bytes)" if files else "none"
    return FileDistributionResult(
        summary=(
            f"Scanned {len(files)} files under {display_path(path)}; "
            f"truncated={truncated}; extensions={len(extension_rows)}; largest_file={largest_file}."
        ),
        root=display_path(path),
        scanned_files=len(files),
        scan_truncated=truncated,
        max_depth=max_depth,
        extensions=extension_rows,
        largest_files=[RankedPath(path=name, size_bytes=size) for name, size in files[:top_n]],
        largest_directories=[
            RankedPath(path=name, size_bytes=size) for name, size in ranked_directories[:top_n]
        ],
    )


async def monitor_file_metadata(
    path: str,
    duration_seconds: float = 5.0,
    interval_seconds: float = 1.0,
    progress: ProgressCallback | None = None,
) -> FileMetadataResult:
    _validate_sampling(duration_seconds, interval_seconds)
    target = resolve_allowed_path(path)
    if target.is_symlink():
        raise ValueError("symbolic links are not monitored")

    events: list[FileMetadataEvent] = []
    previous = _snapshot(target)
    events.append(FileMetadataEvent(captured_at=utc_now_iso(), event="initial", state=previous))
    loop = asyncio.get_running_loop()
    started = loop.time()

    while True:
        elapsed = loop.time() - started
        if elapsed >= duration_seconds:
            break
        await asyncio.sleep(min(interval_seconds, duration_seconds - elapsed))
        try:
            current = _snapshot(target)
        except FileNotFoundError:
            events.append(
                FileMetadataEvent(
                    captured_at=utc_now_iso(),
                    event="deleted",
                    state=None,
                    previous=previous,
                )
            )
            break
        if current != previous:
            events.append(
                FileMetadataEvent(
                    captured_at=utc_now_iso(),
                    event="changed",
                    state=current,
                    previous=previous,
                )
            )
            previous = current
        if progress is not None:
            elapsed = loop.time() - started
            await progress(min(elapsed / duration_seconds, 1.0), "polling file metadata")

    changed_events = sum(event.event == "changed" for event in events)
    deleted = any(event.event == "deleted" for event in events)
    return FileMetadataResult(
        summary=(
            f"Monitored {display_path(path)} for {duration_seconds:g}s: "
            f"changes={changed_events}; deleted={deleted}; events={len(events)}."
        ),
        path=display_path(path),
        duration_seconds=duration_seconds,
        interval_seconds=interval_seconds,
        events=events,
    )


def _inode_info(path: Path) -> InodeStats | None:
    try:
        stat = os.statvfs(path)
    except (PermissionError, OSError):
        return None
    return InodeStats(total=stat.f_files, free=stat.f_ffree, used=stat.f_files - stat.f_ffree)


def _snapshot(path: Path) -> FileMetadata:
    stat = path.stat(follow_symlinks=False)
    return FileMetadata(
        size_bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(timespec="milliseconds"),
        changed_at=datetime.fromtimestamp(stat.st_ctime, UTC).isoformat(timespec="milliseconds"),
    )


def _validate_sampling(duration_seconds: float, interval_seconds: float) -> None:
    if not 0.1 <= duration_seconds <= 30:
        raise ValueError("duration_seconds must be between 0.1 and 30")
    if not 0.1 <= interval_seconds <= 5:
        raise ValueError("interval_seconds must be between 0.1 and 5")
    if interval_seconds > duration_seconds:
        raise ValueError("interval_seconds must not exceed duration_seconds")
