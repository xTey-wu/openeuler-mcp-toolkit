import pytest

from openeuler_mcp.algorithms.page_replacement import simulate_page_replacement


@pytest.mark.parametrize("algorithm", ["FIFO", "LRU", "CLOCK", "OPT"])
def test_page_replacement_accounting_and_hit_state(algorithm: str) -> None:
    result = simulate_page_replacement([1, 2, 3, 3, 1, 4, 1], 3, algorithm)

    assert result.faults + result.hits == result.reference_length
    assert result.fault_rate + result.hit_rate == pytest.approx(1.0)
    assert all(step.evicted is None for step in result.steps if step.action == "hit")
    assert f"{algorithm} page replacement" in result.summary


def test_optimal_never_has_more_faults_than_comparison_algorithms() -> None:
    pages = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    optimal = simulate_page_replacement(pages, 3, "OPT")
    fifo = simulate_page_replacement(pages, 3, "FIFO")
    lru = simulate_page_replacement(pages, 3, "LRU")

    assert optimal.faults == 7
    assert optimal.faults <= fifo.faults
    assert optimal.faults <= lru.faults


def test_page_replacement_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="frame_count"):
        simulate_page_replacement([1], 0, "LRU")
    with pytest.raises(ValueError, match="unsupported"):
        simulate_page_replacement([1], 1, "random")
    with pytest.raises(ValueError, match="must not be empty"):
        simulate_page_replacement([], 1, "FIFO")
