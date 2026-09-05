"""Deterministic page-replacement simulations."""

from __future__ import annotations

from collections import deque

from openeuler_mcp.models import PageReplacementResult, PageReplacementStep

SUPPORTED_ALGORITHMS = {"FIFO", "LRU", "CLOCK", "OPT"}


def simulate_page_replacement(
    reference_string: list[int],
    frame_count: int = 4,
    algorithm: str = "LRU",
) -> PageReplacementResult:
    algorithm = algorithm.upper()
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(f"unsupported page-replacement algorithm: {algorithm}")
    if frame_count <= 0:
        raise ValueError("frame_count must be greater than zero")
    if frame_count > 10_000:
        raise ValueError("frame_count must not exceed 10000")
    if not reference_string:
        raise ValueError("reference_string must not be empty")
    if len(reference_string) > 100_000:
        raise ValueError("reference_string must not contain more than 100000 pages")

    if algorithm == "FIFO":
        steps, faults, hits = _fifo(reference_string, frame_count)
    elif algorithm == "LRU":
        steps, faults, hits = _lru(reference_string, frame_count)
    elif algorithm == "CLOCK":
        steps, faults, hits = _clock(reference_string, frame_count)
    else:
        steps, faults, hits = _optimal(reference_string, frame_count)

    total = len(reference_string)
    return PageReplacementResult(
        summary=(
            f"{algorithm} page replacement: faults={faults}/{total} ({faults / total:.2%}), "
            f"hits={hits}/{total} ({hits / total:.2%}), frames={frame_count}."
        ),
        algorithm=algorithm,
        frame_count=frame_count,
        reference_length=total,
        faults=faults,
        hits=hits,
        fault_rate=faults / total,
        hit_rate=hits / total,
        steps=steps,
    )


def _fifo(pages: list[int], frame_count: int) -> tuple[list[PageReplacementStep], int, int]:
    queue: deque[int] = deque()
    steps: list[PageReplacementStep] = []
    faults = hits = 0
    for index, page in enumerate(pages):
        evicted: int | None = None
        if page in queue:
            hits += 1
            action = "hit"
        else:
            faults += 1
            action = "fault"
            if len(queue) >= frame_count:
                evicted = queue.popleft()
            queue.append(page)
        steps.append(
            PageReplacementStep(
                step=index,
                page=page,
                frames=list(queue),
                action=action,
                evicted=evicted,
            )
        )
    return steps, faults, hits


def _lru(pages: list[int], frame_count: int) -> tuple[list[PageReplacementStep], int, int]:
    frames: list[int] = []
    last_used: dict[int, int] = {}
    steps: list[PageReplacementStep] = []
    faults = hits = 0
    for index, page in enumerate(pages):
        evicted: int | None = None
        if page in frames:
            hits += 1
            action = "hit"
        else:
            faults += 1
            action = "fault"
            if len(frames) < frame_count:
                frames.append(page)
            else:
                evicted = min(frames, key=last_used.__getitem__)
                frames[frames.index(evicted)] = page
        last_used[page] = index
        steps.append(
            PageReplacementStep(
                step=index,
                page=page,
                frames=list(frames),
                action=action,
                evicted=evicted,
            )
        )
    return steps, faults, hits


def _clock(pages: list[int], frame_count: int) -> tuple[list[PageReplacementStep], int, int]:
    frames: list[int | None] = [None] * frame_count
    use_bits = [0] * frame_count
    hand = 0
    steps: list[PageReplacementStep] = []
    faults = hits = 0

    for index, page in enumerate(pages):
        evicted: int | None = None
        if page in frames:
            hits += 1
            action = "hit"
            use_bits[frames.index(page)] = 1
        else:
            faults += 1
            action = "fault"
            while frames[hand] is not None and use_bits[hand] == 1:
                use_bits[hand] = 0
                hand = (hand + 1) % frame_count
            evicted = frames[hand]
            frames[hand] = page
            use_bits[hand] = 1
            hand = (hand + 1) % frame_count
        steps.append(
            PageReplacementStep(
                step=index,
                page=page,
                frames=list(frames),
                use_bits=list(use_bits),
                action=action,
                evicted=evicted,
                hand=hand,
            )
        )
    return steps, faults, hits


def _optimal(pages: list[int], frame_count: int) -> tuple[list[PageReplacementStep], int, int]:
    frames: list[int] = []
    steps: list[PageReplacementStep] = []
    faults = hits = 0
    for index, page in enumerate(pages):
        evicted: int | None = None
        if page in frames:
            hits += 1
            action = "hit"
        else:
            faults += 1
            action = "fault"
            if len(frames) < frame_count:
                frames.append(page)
            else:
                future = pages[index + 1 :]
                next_use = {
                    resident: future.index(resident) if resident in future else float("inf")
                    for resident in frames
                }
                evicted = max(frames, key=next_use.__getitem__)
                frames[frames.index(evicted)] = page
        steps.append(
            PageReplacementStep(
                step=index,
                page=page,
                frames=list(frames),
                action=action,
                evicted=evicted,
            )
        )
    return steps, faults, hits
