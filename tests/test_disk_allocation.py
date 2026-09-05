import pytest

from openeuler_mcp.algorithms.disk import simulate_disk_allocation
from openeuler_mcp.models import DiskFileInput, DiskScenario


def test_failed_linked_allocation_rolls_back() -> None:
    scenario = DiskScenario(
        total_blocks=3,
        files=[
            DiskFileInput(name="too-large", size_bytes=4 * 4096),
            DiskFileInput(name="small", size_bytes=4096),
        ],
    )
    result = simulate_disk_allocation(scenario, "linked", 4096)

    assert result.allocations[0].allocated is False
    assert result.allocations[0].data_blocks == []
    assert result.allocations[1].allocated is True
    assert result.allocations[1].data_blocks == [0]
    assert result.free_blocks == 2
    assert "allocated=1/2 files" in result.summary


def test_indexed_allocation_accounts_for_index_block() -> None:
    scenario = DiskScenario(
        total_blocks=4,
        files=[DiskFileInput(name="A", size_bytes=2 * 4096)],
    )
    result = simulate_disk_allocation(scenario, "indexed", 4096)

    allocation = result.allocations[0]
    assert allocation.index_block == 0
    assert allocation.data_blocks == [1, 2]
    assert result.free_blocks == 1
    assert result.free_block_ratio == pytest.approx(0.25)


def test_empty_file_does_not_consume_simulated_blocks() -> None:
    scenario = DiskScenario(
        total_blocks=2,
        files=[DiskFileInput(name="empty", size_bytes=0)],
    )
    result = simulate_disk_allocation(scenario, "indexed", 4096)

    assert result.allocations[0].allocated is True
    assert result.allocations[0].index_block is None
    assert result.free_blocks == 2


def test_disk_allocation_rejects_duplicate_names_and_bad_block_size() -> None:
    scenario = DiskScenario(
        files=[DiskFileInput(name="A", size_bytes=1), DiskFileInput(name="A", size_bytes=2)]
    )
    with pytest.raises(ValueError, match="unique"):
        simulate_disk_allocation(scenario)
    with pytest.raises(ValueError, match="greater than zero"):
        simulate_disk_allocation(
            DiskScenario(files=[DiskFileInput(name="A", size_bytes=1)]),
            block_size_bytes=0,
        )
