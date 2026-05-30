"""End-to-end test for dual parallel session lifecycle and isolation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_dual_parallel_sessions_isolated_cleanup():
    s1 = "test-e2e-parallel-1"
    s2 = "test-e2e-parallel-2"

    try:
        p1 = _run(
            [
                PYTHON,
                str(REPO / "scripts" / "launch_parallel_session.py"),
                "--session-id",
                s1,
                "--no-open",
            ]
        )
        assert p1.returncode == 0, p1.stderr or p1.stdout

        p2 = _run(
            [
                PYTHON,
                str(REPO / "scripts" / "launch_parallel_session.py"),
                "--session-id",
                s2,
                "--no-open",
            ]
        )
        assert p2.returncode == 0, p2.stderr or p2.stdout

        listed = _run([PYTHON, str(REPO / "scripts" / "active_sessions.py"), "list"])
        assert listed.returncode == 0, listed.stderr or listed.stdout
        data = json.loads(listed.stdout)
        items = {item["session_id"]: item for item in data.get("items", [])}
        assert s1 in items and s2 in items

        w1 = Path(items[s1].get("worktree_path") or "").resolve()
        w2 = Path(items[s2].get("worktree_path") or "").resolve()
        assert w1 and w2 and w1 != w2
        assert w1.is_dir() and w2.is_dir()

        assert items[s1].get("lock_path")
        assert items[s2].get("lock_path")
        assert items[s1].get("lock_path") != items[s2].get("lock_path")
    finally:
        _run([PYTHON, str(REPO / "scripts" / "active_sessions.py"), "end", s1])
        _run([PYTHON, str(REPO / "scripts" / "active_sessions.py"), "end", s2])
        _run([PYTHON, str(REPO / "scripts" / "session_worktree.py"), "remove", s1])
        _run([PYTHON, str(REPO / "scripts" / "session_worktree.py"), "remove", s2])
