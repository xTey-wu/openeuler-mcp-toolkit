from pathlib import Path

import pytest

from openeuler_mcp.config import resolve_allowed_path
from openeuler_mcp.services.filesystem import analyze_file_distribution


def test_path_must_remain_inside_allowed_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setenv("OPENEULER_MCP_ALLOWED_ROOTS", str(allowed))

    assert resolve_allowed_path(str(allowed)) == allowed.resolve()
    with pytest.raises(ValueError, match="outside"):
        resolve_allowed_path(str(outside))


def test_distribution_skips_symbolic_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (allowed / "visible.txt").write_text("ok", encoding="utf-8")
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    (allowed / "escape").symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("OPENEULER_MCP_ALLOWED_ROOTS", str(allowed))

    result = analyze_file_distribution(str(allowed), max_depth=3)

    assert result.scanned_files == 1
    assert [item.path for item in result.largest_files] == ["visible.txt"]
    assert "largest_file=visible.txt" in result.summary


def test_distribution_limits_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENEULER_MCP_ALLOWED_ROOTS", str(tmp_path))
    for index in range(5):
        (tmp_path / f"{index}.txt").write_text("x" * (index + 1), encoding="utf-8")

    result = analyze_file_distribution(str(tmp_path), max_files=2)

    assert result.scanned_files == 2
    assert result.scan_truncated is True
