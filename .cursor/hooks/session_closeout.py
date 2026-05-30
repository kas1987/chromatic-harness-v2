#!/usr/bin/env python3
"""Cursor sessionEnd hook: budget-aware session closeout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_CLOSEOUT = _REPO / "scripts" / "session_closeout.py"
_ACTIVE = _REPO / "scripts" / "active_sessions.py"
_WORKTREE = _REPO / "scripts" / "session_worktree.py"
_SESSION_ID_FILE = _REPO / ".agents" / "handoffs" / "cursor_session_id.txt"


def _load_session_id() -> str:
    if not _SESSION_ID_FILE.is_file():
        return ""
    return _SESSION_ID_FILE.read_text(encoding="utf-8").strip()


def _unregister_active_session(session_id: str) -> None:
    if not session_id or not _ACTIVE.is_file():
        return
    subprocess.run(
        [sys.executable, str(_ACTIVE), "end", session_id],
        cwd=_REPO,
        timeout=30,
        check=False,
    )
    if _WORKTREE.is_file():
        subprocess.run(
            [sys.executable, str(_WORKTREE), "remove", session_id],
            cwd=_REPO,
            timeout=60,
            check=False,
        )
    try:
        _SESSION_ID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def main() -> int:
    if not _CLOSEOUT.is_file():
        return 0
    r = subprocess.run(
        [sys.executable, str(_CLOSEOUT), "--invoked-by", "cursor"],
        cwd=_REPO,
        timeout=180,
        check=False,
    )
    _unregister_active_session(_load_session_id())
    return 0 if r.returncode in (0, 124) else 0


if __name__ == "__main__":
    raise SystemExit(main())
