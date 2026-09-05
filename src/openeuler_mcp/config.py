"""Runtime configuration and filesystem access controls."""

from __future__ import annotations

import os
from pathlib import Path

ALLOWED_ROOTS_ENV = "OPENEULER_MCP_ALLOWED_ROOTS"


def allowed_roots() -> tuple[Path, ...]:
    """Return resolved roots that filesystem tools may inspect.

    Multiple roots use the platform path separator (":" on Linux/macOS).
    The server's current working directory is the secure default.
    """

    configured = os.getenv(ALLOWED_ROOTS_ENV)
    raw_roots = configured.split(os.pathsep) if configured else [str(Path.cwd())]
    roots: list[Path] = []
    for value in raw_roots:
        value = value.strip()
        if not value:
            continue
        root = Path(value).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError(f"{ALLOWED_ROOTS_ENV} entries must be directories")
        roots.append(root)
    if not roots:
        raise ValueError(f"{ALLOWED_ROOTS_ENV} does not contain a usable directory")
    return tuple(dict.fromkeys(roots))


def resolve_allowed_path(path: str) -> Path:
    """Resolve an existing path and reject access outside configured roots."""

    if not path or not path.strip():
        raise ValueError("path must not be empty")
    try:
        candidate = Path(path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("path does not exist or cannot be resolved") from exc

    if not any(candidate == root or candidate.is_relative_to(root) for root in allowed_roots()):
        raise ValueError("path is outside OPENEULER_MCP_ALLOWED_ROOTS")
    return candidate


def display_path(requested: str) -> str:
    """Return the user-supplied path without exposing extra host path data."""

    return str(Path(requested).expanduser())
