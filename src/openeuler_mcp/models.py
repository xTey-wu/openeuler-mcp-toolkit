"""Validated input and structured output models for all public tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MemoryStats(StrictModel):
    total_bytes: int
    available_bytes: int
    used_bytes: int
    free_bytes: int
    cached_bytes: int | None = None
    buffers_bytes: int | None = None
    percent: float


class SwapStats(StrictModel):
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float
    swapped_in_bytes: int
    swapped_out_bytes: int


class MemoryInfoResult(StrictModel):
    summary: str
    captured_at: str
    memory: MemoryStats
    swap: SwapStats | None
    proc_meminfo: dict[str, str] | None = None
    source: str


class MemoryMapping(StrictModel):
    path: str
    rss_bytes: int
    size_bytes: int
    private_bytes: int | None = None
    shared_bytes: int | None = None


class ProcessMemoryResult(StrictModel):
    summary: str
    captured_at: str
    pid: int
    name: str
    rss_bytes: int
    vms_bytes: int
    mappings: list[MemoryMapping]
    returned_mappings: int
    total_mappings: int
    source: str


class MemoryTrendSample(StrictModel):
    captured_at: str
    used_bytes: int
    available_bytes: int
    percent: float


class MemoryTrendResult(StrictModel):
    summary: str
    trend: Literal["increasing", "decreasing", "stable"]
    change_ratio: float
    samples: list[MemoryTrendSample]
    duration_seconds: float
    interval_seconds: float


class PageReplacementStep(StrictModel):
    step: int
    page: int
    frames: list[int | None]
    action: Literal["hit", "fault"]
    evicted: int | None = None
    use_bits: list[int] | None = None
    hand: int | None = None


class PageReplacementResult(StrictModel):
    summary: str
    algorithm: Literal["FIFO", "LRU", "CLOCK", "OPT"]
    frame_count: int
    reference_length: int
    faults: int
    hits: int
    fault_rate: float
    hit_rate: float
    steps: list[PageReplacementStep]


class InodeStats(StrictModel):
    total: int
    used: int
    free: int


class PartitionInfo(StrictModel):
    device: str
    mountpoint: str
    filesystem_type: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float
    inodes: InodeStats | None = None


class FilesystemInfoResult(StrictModel):
    summary: str
    captured_at: str
    partitions: list[PartitionInfo]


class ExtensionStats(StrictModel):
    extension: str
    file_count: int
    total_bytes: int


class RankedPath(StrictModel):
    path: str
    size_bytes: int


class FileDistributionResult(StrictModel):
    summary: str
    root: str
    scanned_files: int
    scan_truncated: bool
    max_depth: int
    extensions: list[ExtensionStats]
    largest_files: list[RankedPath]
    largest_directories: list[RankedPath]


class FileMetadata(StrictModel):
    size_bytes: int
    modified_at: str
    changed_at: str


class FileMetadataEvent(StrictModel):
    captured_at: str
    event: Literal["initial", "changed", "deleted"]
    state: FileMetadata | None
    previous: FileMetadata | None = None


class FileMetadataResult(StrictModel):
    summary: str
    path: str
    duration_seconds: float
    interval_seconds: float
    events: list[FileMetadataEvent]
    method: Literal["metadata_polling"] = "metadata_polling"


class DiskFileInput(StrictModel):
    name: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(ge=0)


class DiskScenario(StrictModel):
    files: list[DiskFileInput] = Field(min_length=1, max_length=256)
    total_blocks: int = Field(default=128, ge=1, le=100_000)


class DiskAllocation(StrictModel):
    file: str
    size_bytes: int
    data_blocks_needed: int
    allocated: bool
    data_blocks: list[int]
    index_block: int | None = None


class DiskAllocationResult(StrictModel):
    summary: str
    strategy: Literal["contiguous", "linked", "indexed"]
    block_size_bytes: int
    total_blocks: int
    free_blocks: int
    free_block_ratio: float
    largest_free_extent_blocks: int
    external_fragmentation_ratio: float
    allocations: list[DiskAllocation]
    block_map_preview: list[str | None]


class ProcessNode(StrictModel):
    pid: int
    name: str | None
    user: str | None
    children: list[ProcessNode] = Field(default_factory=list)


class ProcessTreeResult(StrictModel):
    summary: str
    captured_at: str
    root_pid: int
    max_depth: int
    returned_nodes: int
    truncated: bool
    tree: ProcessNode


class ContextSwitchSample(StrictModel):
    captured_at: str
    voluntary_delta: int | None = None
    involuntary_delta: int | None = None
    total_delta: int


class ContextSwitchResult(StrictModel):
    summary: str
    scope: Literal["system", "process"]
    pid: int | None = None
    duration_seconds: float
    interval_seconds: float
    samples: list[ContextSwitchSample]


class CpuJobInput(StrictModel):
    pid: str = Field(min_length=1, max_length=64)
    arrival: float = Field(default=0, ge=0)
    burst: float = Field(gt=0)
    priority: int = 0


class ScheduleSlice(StrictModel):
    pid: str
    start: float
    finish: float
    duration: float
    priority: int | None = None


class JobScheduleMetrics(StrictModel):
    pid: str
    completion: float
    turnaround: float
    waiting: float
    response: float


class ScheduleMetrics(StrictModel):
    average_waiting: float
    average_turnaround: float
    average_response: float


class CpuSchedulingResult(StrictModel):
    summary: str
    algorithm: Literal["FCFS", "SJF", "RR", "PRIORITY"]
    time_slice: float | None = None
    timeline: list[ScheduleSlice]
    jobs: list[JobScheduleMetrics]
    metrics: ScheduleMetrics


class CpuTimeSample(StrictModel):
    captured_at: str
    ratios: dict[str, float]


class CpuTimeRatioResult(StrictModel):
    summary: str
    duration_seconds: float
    interval_seconds: float
    samples: list[CpuTimeSample]


ProcessNode.model_rebuild()
