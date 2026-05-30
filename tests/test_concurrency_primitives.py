"""Tests for concurrent session primitives (locks, registry, worktree helpers)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_session_lock_context_roundtrip(tmp_path, monkeypatch):
    import concurrency.session_lock as sl

    monkeypatch.setattr(sl, "LOCK_DB", tmp_path / "locks.sqlite3")

    with sl.session_lock("unit-lock", session_id="s1", timeout_seconds=1.0):
        conn = sl._ensure_db()  # noqa: SLF001 - test internal storage behavior
        try:
            row = conn.execute(
                "SELECT owner_session_id FROM session_locks WHERE lock_name = ?",
                ("unit-lock",),
            ).fetchone()
        finally:
            conn.close()
        assert row and row[0] == "s1"

    conn = sl._ensure_db()  # noqa: SLF001 - test internal cleanup behavior
    try:
        row = conn.execute(
            "SELECT owner_session_id FROM session_locks WHERE lock_name = ?",
            ("unit-lock",),
        ).fetchone()
    finally:
        conn.close()
    assert row is None


def test_active_sessions_start_list_end_with_paths():
    sid = "test-concurrency-session"
    start = subprocess.run(
        [
            PYTHON,
            str(REPO / "scripts" / "active_sessions.py"),
            "start",
            "--invoked-by",
            "pytest",
            "--session-id",
            sid,
            "--worktree-path",
            ".worktrees/test-concurrency-session",
            "--lock-path",
            ".agents/locks/test-concurrency-session.lock",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert start.returncode == 0, start.stderr or start.stdout

    listed = subprocess.run(
        [PYTHON, str(REPO / "scripts" / "active_sessions.py"), "list"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr or listed.stdout
    data = json.loads(listed.stdout)
    match = [item for item in data.get("items", []) if item.get("session_id") == sid]
    assert match, listed.stdout
    assert match[0].get("worktree_path") == ".worktrees/test-concurrency-session"
    assert match[0].get("lock_path") == ".agents/locks/test-concurrency-session.lock"

    end = subprocess.run(
        [PYTHON, str(REPO / "scripts" / "active_sessions.py"), "end", sid],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert end.returncode == 0, end.stderr or end.stdout


def test_session_worktree_safe_name():
    from scripts import session_worktree as sw

    assert sw._safe_name("cursor session/1") == "cursor-session-1"  # noqa: SLF001
    assert sw._safe_name("...") == "session"  # noqa: SLF001
