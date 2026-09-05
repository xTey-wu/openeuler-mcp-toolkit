"""Transactional simulations for disk-block allocation."""

from __future__ import annotations

from math import ceil

from openeuler_mcp.models import (
    DiskAllocation,
    DiskAllocationResult,
    DiskScenario,
)

SUPPORTED_STRATEGIES = {"contiguous", "linked", "indexed"}


def simulate_disk_allocation(
    scenario: DiskScenario,
    strategy: str = "contiguous",
    block_size_bytes: int = 4096,
) -> DiskAllocationResult:
    strategy = strategy.lower()
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(f"unsupported disk allocation strategy: {strategy}")
    if block_size_bytes <= 0:
        raise ValueError("block_size_bytes must be greater than zero")
    if block_size_bytes > 1024 * 1024 * 1024:
        raise ValueError("block_size_bytes must not exceed 1 GiB")

    names = [item.name for item in scenario.files]
    if len(names) != len(set(names)):
        raise ValueError("file names must be unique")

    block_map: list[str | None] = [None] * scenario.total_blocks
    allocations: list[DiskAllocation] = []
    for file in scenario.files:
        data_blocks_needed = ceil(file.size_bytes / block_size_bytes) if file.size_bytes else 0
        data_blocks: list[int] = []
        index_block: int | None = None

        if data_blocks_needed == 0:
            allocated = True
        elif strategy == "contiguous":
            data_blocks = _find_contiguous(block_map, data_blocks_needed)
        elif strategy == "linked":
            data_blocks = _find_free(block_map, data_blocks_needed)
        else:
            selected = _find_free(block_map, data_blocks_needed + 1)
            if len(selected) == data_blocks_needed + 1:
                index_block, *data_blocks = selected

        if data_blocks_needed > 0:
            required_found = len(data_blocks) == data_blocks_needed
            allocated = required_found and (strategy != "indexed" or index_block is not None)

        # Commit only complete allocations. Failed attempts leave the block map unchanged.
        if allocated:
            if index_block is not None:
                block_map[index_block] = f"{file.name}:index"
            for block in data_blocks:
                block_map[block] = file.name
        else:
            data_blocks = []
            index_block = None

        allocations.append(
            DiskAllocation(
                file=file.name,
                size_bytes=file.size_bytes,
                data_blocks_needed=data_blocks_needed,
                allocated=allocated,
                data_blocks=data_blocks,
                index_block=index_block,
            )
        )

    free_blocks = block_map.count(None)
    largest_extent = _largest_free_extent(block_map)
    external_fragmentation = 0.0 if free_blocks == 0 else 1 - largest_extent / free_blocks
    allocated_count = sum(item.allocated for item in allocations)
    return DiskAllocationResult(
        summary=(
            f"{strategy} allocation: allocated={allocated_count}/{len(allocations)} files; "
            f"free_blocks={free_blocks}/{scenario.total_blocks}; "
            f"block_size={block_size_bytes} bytes."
        ),
        strategy=strategy,
        block_size_bytes=block_size_bytes,
        total_blocks=scenario.total_blocks,
        free_blocks=free_blocks,
        free_block_ratio=free_blocks / scenario.total_blocks,
        largest_free_extent_blocks=largest_extent,
        external_fragmentation_ratio=external_fragmentation,
        allocations=allocations,
        block_map_preview=block_map[: min(64, scenario.total_blocks)],
    )


def _find_free(block_map: list[str | None], count: int) -> list[int]:
    if count == 0:
        return []
    selected = [index for index, owner in enumerate(block_map) if owner is None][:count]
    return selected if len(selected) == count else []


def _find_contiguous(block_map: list[str | None], count: int) -> list[int]:
    if count == 0:
        return []
    current: list[int] = []
    for index, owner in enumerate(block_map):
        if owner is None:
            current.append(index)
            if len(current) == count:
                return current
        else:
            current = []
    return []


def _largest_free_extent(block_map: list[str | None]) -> int:
    best = current = 0
    for owner in block_map:
        if owner is None:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best
