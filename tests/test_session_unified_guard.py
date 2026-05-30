"""Tests for session_unified_guard codegraph freshness check.

Run with: pytest tests/test_session_unified_guard.py -v

Covers bead chromatic-harness-v2-bsah: the freshness check must be advisory
(never fail the guard) and correctly classify absent / fresh / stale indexes.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "session_unified_guard.py"


def _load_module(repo_override: Path):
    spec = importlib.util.spec_from_file_location("session_unified_guard", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    mod.REPO = repo_override  # redirect at module scope
    return mod


def _make_db(repo: Path, mtime: float) -> Path:
    cg = repo / ".codegraph"
    cg.mkdir(parents=True, exist_ok=True)
    db = cg / "codegraph.db"
    db.write_bytes(b"fake")
    os.utime(db, (mtime, mtime))
    return db


def _make_source(repo: Path, name: str, mtime: float) -> Path:
    f = repo / name
    f.write_text("x = 1\n", encoding="utf-8")
    os.utime(f, (mtime, mtime))
    return f


def test_absent_index_is_advisory(tmp_path):
    mod = _load_module(tmp_path)
    result = mod._codegraph_freshness()
    assert result["status"] == "absent"
    assert result["ok"] is True  # never blocks the guard


def test_fresh_index_when_db_newer_than_source(tmp_path):
    mod = _load_module(tmp_path)
    _make_source(tmp_path, "a.py", mtime=1000.0)
    _make_db(tmp_path, mtime=2000.0)  # indexed after source changed
    result = mod._codegraph_freshness()
    assert result["status"] == "fresh"
    assert result["ok"] is True
    assert result["index_lag_minutes"] == 0.0


def test_stale_index_when_source_newer_than_db(tmp_path):
    mod = _load_module(tmp_path)
    db_time = 1000.0
    _make_db(tmp_path, mtime=db_time)
    # source edited ~2h after last index → beyond the 60m default threshold
    _make_source(tmp_path, "a.py", mtime=db_time + 2 * 3600)
    result = mod._codegraph_freshness(stale_after_minutes=60)
    assert result["status"] == "stale"
    assert result["ok"] is True  # advisory even when stale
    assert result["index_lag_minutes"] == pytest.approx(120.0, abs=0.5)
    assert result["newest_source"] == "a.py"


def test_skip_dirs_are_ignored(tmp_path):
    mod = _load_module(tmp_path)
    db_time = 1000.0
    _make_db(tmp_path, mtime=db_time)
    # a "newer" file but inside node_modules must not mark the index stale
    nm = tmp_path / "node_modules"
    nm.mkdir()
    _make_source(nm, "junk.js", mtime=db_time + 9999)
    _make_source(tmp_path, "real.py", mtime=db_time - 500)  # older than db
    result = mod._codegraph_freshness(stale_after_minutes=60)
    assert result["status"] == "fresh"
