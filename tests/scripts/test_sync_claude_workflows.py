"""Tests for the cross-platform lite-workflow installer (self-provisioning)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "scripts" / "sync_claude_workflows.py"

_spec = importlib.util.spec_from_file_location("sync_claude_workflows", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_workflows"] = sync_mod
_spec.loader.exec_module(sync_mod)


@pytest.fixture()
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Point the installer at a temp src + home so it never touches the real ~/.claude."""
    src = tmp_path / "repo" / ".claude" / "workflows"
    src.mkdir(parents=True)
    (src / "ship.js").write_text("// ship\n", encoding="utf-8")
    (src / "qa.js").write_text("// qa\n", encoding="utf-8")
    (src / "ship.HEAVY.js.bak").write_text("// heavy archived\n", encoding="utf-8")

    dest = tmp_path / "home" / ".claude" / "workflows"
    monkeypatch.setattr(sync_mod, "SRC", src)
    monkeypatch.setattr(sync_mod, "DEST", dest)
    return src, dest


def test_sync_installs_lite_workflows(fake_repo: tuple[Path, Path]) -> None:
    _src, dest = fake_repo
    assert sync_mod.sync(quiet=True) == 0
    assert (dest / "ship.js").is_file()
    assert (dest / "qa.js").is_file()
    # Heavy archived workflows are never installed.
    assert not (dest / "ship.HEAVY.js.bak").exists()


def test_sync_backs_up_changed_workflow(fake_repo: tuple[Path, Path]) -> None:
    _src, dest = fake_repo
    dest.mkdir(parents=True)
    (dest / "ship.js").write_text("// OLD content\n", encoding="utf-8")

    assert sync_mod.sync(quiet=True) == 0
    assert (dest / "ship.js.pre-sync.bak").is_file()
    assert (dest / "ship.js.pre-sync.bak").read_text() == "// OLD content\n"
    assert (dest / "ship.js").read_text() == "// ship\n"


def test_check_reports_drift_then_clean(fake_repo: tuple[Path, Path]) -> None:
    # Before install: every lite workflow is drift.
    drift = sync_mod.check()
    assert set(drift) == {"ship.js", "qa.js"}

    sync_mod.sync(quiet=True)
    assert sync_mod.check() == []


def test_sync_missing_source_returns_error(fake_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_mod, "SRC", Path("/nonexistent/workflows"))
    assert sync_mod.sync(quiet=True) == 1
