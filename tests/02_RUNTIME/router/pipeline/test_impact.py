"""Tests for router pipeline impact stage."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "02_RUNTIME"))

import pytest

from router.pipeline.impact import (
    extract_file_refs,
    count_impacted,
    impact_fan_out,
    IMPACT_ENABLED,
)


# ── extract_file_refs ─────────────────────────────────────────────────────────


def test_extract_file_refs_empty_string():
    """Empty text yields no file refs."""
    with patch("router.pipeline.impact._repo", return_value=Path("/")):
        result = extract_file_refs("")
    assert result == []


def test_extract_file_refs_no_known_files(tmp_path):
    """Returns empty list when referenced files do not exist on disk."""
    text = "see scripts/nonexistent_file.py for details"
    with patch("router.pipeline.impact._repo", return_value=tmp_path):
        result = extract_file_refs(text)
    assert result == []


def test_extract_file_refs_finds_existing_file(tmp_path):
    """Returns paths for file references that exist on disk."""
    # Create a real file in tmp_path
    subdir = tmp_path / "scripts"
    subdir.mkdir()
    real_file = subdir / "helper.py"
    real_file.write_text("# helper\n", encoding="utf-8")

    text = f"edit scripts/helper.py to fix the bug"
    with patch("router.pipeline.impact._repo", return_value=tmp_path):
        result = extract_file_refs(text)

    assert "scripts/helper.py" in result


def test_extract_file_refs_deduplicates(tmp_path):
    """Each unique file path appears at most once."""
    subdir = tmp_path / "src"
    subdir.mkdir()
    (subdir / "mod.py").write_text("", encoding="utf-8")

    text = "update src/mod.py, then review src/mod.py"
    with patch("router.pipeline.impact._repo", return_value=tmp_path):
        result = extract_file_refs(text)

    assert result.count("src/mod.py") == 1


def test_extract_file_refs_multiple_files(tmp_path):
    """Multiple distinct existing files are all collected."""
    for name in ("a.py", "b.py", "c.yaml"):
        (tmp_path / name).write_text("", encoding="utf-8")

    text = "change a.py and b.py then edit c.yaml"
    with patch("router.pipeline.impact._repo", return_value=tmp_path):
        result = extract_file_refs(text)

    assert len(result) == 3


def test_extract_file_refs_strips_punctuation(tmp_path):
    """Surrounding punctuation (backticks, parens, commas) is stripped."""
    (tmp_path / "util.py").write_text("", encoding="utf-8")

    text = "see `util.py` for more"
    with patch("router.pipeline.impact._repo", return_value=tmp_path):
        result = extract_file_refs(text)

    assert "util.py" in result


# ── count_impacted ────────────────────────────────────────────────────────────


def test_count_impacted_empty_output():
    """Empty stdout returns 0."""
    assert count_impacted("") == 0


def test_count_impacted_none_output():
    """None stdout returns 0."""
    assert count_impacted(None) == 0  # type: ignore[arg-type]


def test_count_impacted_single_path():
    """One path-like line returns 1."""
    assert count_impacted("src/module.py\n") == 1


def test_count_impacted_multiple_paths():
    """Counts distinct path-like lines."""
    stdout = "src/a.py\nsrc/b.py\ntests/test_a.py\n"
    assert count_impacted(stdout) == 3


def test_count_impacted_deduplicates():
    """Duplicate path lines count as one."""
    stdout = "src/a.py\nsrc/a.py\nsrc/a.py\n"
    assert count_impacted(stdout) == 1


def test_count_impacted_ignores_blank_lines():
    """Blank lines are not counted."""
    stdout = "\nsrc/a.py\n\nsrc/b.py\n\n"
    assert count_impacted(stdout) == 2


def test_count_impacted_windows_paths():
    """Windows-style paths are counted as path-like."""
    stdout = "src\\module.py\nsrc\\helper.py\n"
    assert count_impacted(stdout) == 2


# ── impact_fan_out ────────────────────────────────────────────────────────────


def test_impact_fan_out_returns_none_when_disabled(monkeypatch):
    """Returns None when IMPACT_ENABLED is False (default)."""
    import router.pipeline.impact as imp

    monkeypatch.setattr(imp, "IMPACT_ENABLED", False)
    result = impact_fan_out("fix router.py", "edit router.py")
    assert result is None


def test_impact_fan_out_returns_none_when_no_file_refs(monkeypatch, tmp_path):
    """Returns None when no files are referenced in description+prompt."""
    import router.pipeline.impact as imp

    monkeypatch.setattr(imp, "IMPACT_ENABLED", True)
    with patch("router.pipeline.impact._repo", return_value=tmp_path):
        result = impact_fan_out("nothing here", "no files mentioned")
    assert result is None


def test_impact_fan_out_uses_custom_runner(monkeypatch, tmp_path):
    """Calls runner with file refs and returns max(count, len(refs))."""
    import router.pipeline.impact as imp

    monkeypatch.setattr(imp, "IMPACT_ENABLED", True)

    # Create real files so extract_file_refs can find them
    (tmp_path / "router.py").write_text("", encoding="utf-8")
    (tmp_path / "policy.py").write_text("", encoding="utf-8")

    runner_calls: list[list[str]] = []

    def fake_runner(files: list[str]) -> str:
        runner_calls.append(files)
        return "router.py\npolicy.py\ncontracts.py\n"

    with patch("router.pipeline.impact._repo", return_value=tmp_path):
        result = impact_fan_out("edit router.py and policy.py", "", runner=fake_runner)

    assert runner_calls, "Runner should have been called"
    # result = max(count(3), len(refs=2)) = 3
    assert result == 3


def test_impact_fan_out_minimum_is_len_refs(monkeypatch, tmp_path):
    """Result is at least len(refs) even if runner returns fewer paths."""
    import router.pipeline.impact as imp

    monkeypatch.setattr(imp, "IMPACT_ENABLED", True)

    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "b.py").write_text("", encoding="utf-8")
    (tmp_path / "c.py").write_text("", encoding="utf-8")

    def minimal_runner(files):
        return "a.py\n"  # only 1 path returned

    with patch("router.pipeline.impact._repo", return_value=tmp_path):
        result = impact_fan_out("change a.py b.py c.py", "", runner=minimal_runner)

    # max(1, 3) = 3
    assert result == 3


def test_impact_fan_out_is_fail_open(monkeypatch, tmp_path):
    """Returns None on exception (fail-open)."""
    import router.pipeline.impact as imp

    monkeypatch.setattr(imp, "IMPACT_ENABLED", True)

    (tmp_path / "x.py").write_text("", encoding="utf-8")

    def crashing_runner(files):
        raise RuntimeError("codegraph not found")

    with patch("router.pipeline.impact._repo", return_value=tmp_path):
        result = impact_fan_out("edit x.py", "", runner=crashing_runner)

    assert result is None


def test_impact_fan_out_boundary_single_file(monkeypatch, tmp_path):
    """Works correctly when exactly one file is referenced."""
    import router.pipeline.impact as imp

    monkeypatch.setattr(imp, "IMPACT_ENABLED", True)
    (tmp_path / "solo.py").write_text("", encoding="utf-8")

    def runner(files):
        return "solo.py\n"

    with patch("router.pipeline.impact._repo", return_value=tmp_path):
        result = impact_fan_out("update solo.py", "", runner=runner)

    assert result == 1
