#!/usr/bin/env python3
"""Cursor sessionStart hook: run harness pre-session boot automation."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_GUARD = _REPO / "scripts" / "session_unified_guard.py"
_ACTIVE = _REPO / "scripts" / "active_sessions.py"
_WORKTREE = _REPO / "scripts" / "session_worktree.py"
_SESSION_ID_FILE = _REPO / ".agents" / "handoffs" / "cursor_session_id.txt"
_LOCKS_DIR = _REPO / ".agents" / "locks"


def _session_id() -> str:
    sid = os.environ.get("CHROMATIC_SESSION_ID", "").strip()
    if sid:
        return sid
    generated = f"cursor-{uuid.uuid4()}"
    _SESSION_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSION_ID_FILE.write_text(generated, encoding="utf-8")
    return generated


def _register_active_session(session_id: str) -> None:
    if not _ACTIVE.is_file():
        return
    worktree_path = _ensure_worktree(session_id)
    lock_path = _lock_path(session_id)
    subprocess.run(
        [
            sys.executable,
            str(_ACTIVE),
            "start",
            "--invoked-by",
            "cursor",
            "--session-id",
            session_id,
            "--worktree-path",
            worktree_path,
            "--lock-path",
            lock_path,
        ],
        cwd=_REPO,
        timeout=30,
        check=False,
    )


def _lock_path(session_id: str) -> str:
    _LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    return str((_LOCKS_DIR / f"{session_id}.lock").resolve())


def _ensure_worktree(session_id: str) -> str:
    if not _WORKTREE.is_file():
        return ""
    proc = subprocess.run(
        [sys.executable, str(_WORKTREE), "ensure", session_id],
        cwd=_REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    try:
        import json

        payload = json.loads(proc.stdout or "{}")
        return str(payload.get("worktree_path", ""))
    except Exception:
        return ""


def main() -> int:
    session_id = _session_id()
    _register_active_session(session_id)
    if not _GUARD.is_file():
        print("session_unified_guard.py missing", file=sys.stderr)
        return 0
    r = subprocess.run(
        [
            sys.executable,
            str(_GUARD),
            "--surface",
            "ide",
            "--invoked-by",
            "cursor",
        ],
        cwd=_REPO,
        timeout=300,
        check=False,
    )
    return 0 if r.returncode in (0, 124) else 0


if __name__ == "__main__":
    raise SystemExit(main())
