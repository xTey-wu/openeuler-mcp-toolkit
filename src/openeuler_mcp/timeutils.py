"""Time helpers shared by service modules."""

from datetime import UTC, datetime


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")
