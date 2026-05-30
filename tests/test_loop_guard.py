"""Tests for the router loop-iteration guard (bead chromatic-harness-v2-ks05).

Run with: pytest tests/test_loop_guard.py -v
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


_RUNTIME = Path(__file__).resolve().parents[1] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

lg = importlib.import_module("router.loop_guard")


def test_signature_stable_and_normalized():
    a = lg.task_signature("Refactor   the  gate", "general-purpose")
    b = lg.task_signature("refactor the gate", "general-purpose")
    assert a == b  # whitespace + case normalized
    assert a != lg.task_signature("refactor the gate", "code-reviewer")


def test_escalates_ok_warn_block(tmp_path, monkeypatch):
    monkeypatch.setattr(lg, "WARN_THRESHOLD", 3)
    monkeypatch.setattr(lg, "BLOCK_THRESHOLD", 5)
    levels = []
    for _ in range(7):
        v = lg.bump_and_check(
            "same task", "general-purpose", repo_root=tmp_path, session_id="s1"
        )
        levels.append(v["level"])
    # counts 1,2,3 -> ok ; 4,5 -> warn ; 6,7 -> block
    assert levels == ["ok", "ok", "ok", "warn", "warn", "block", "block"]


def test_distinct_tasks_counted_separately(tmp_path):
    v1 = lg.bump_and_check("task A", repo_root=tmp_path, session_id="s2")
    v2 = lg.bump_and_check("task B", repo_root=tmp_path, session_id="s2")
    assert v1["count"] == 1 and v2["count"] == 1


def test_new_session_resets_counts(tmp_path):
    for _ in range(4):
        lg.bump_and_check("loopy", repo_root=tmp_path, session_id="old")
    fresh = lg.bump_and_check("loopy", repo_root=tmp_path, session_id="new")
    assert fresh["count"] == 1


def test_advisory_note_text(monkeypatch):
    monkeypatch.setattr(lg, "WARN_THRESHOLD", 3)
    monkeypatch.setattr(lg, "BLOCK_THRESHOLD", 5)
    assert lg.advisory_note({"level": "ok", "count": 1}) == ""
    assert "LOOP WARN" in lg.advisory_note({"level": "warn", "count": 4})
    assert "LOOP BLOCK" in lg.advisory_note({"level": "block", "count": 6})


def test_fail_open_on_bad_path(monkeypatch):
    # Force write to fail by pointing at a path that can't be created.
    v = lg.bump_and_check("x", repo_root=Path("\x00illegal"), session_id="s")
    assert v["ok"] is False
    assert v["level"] == "ok"  # never blocks on guard malfunction
