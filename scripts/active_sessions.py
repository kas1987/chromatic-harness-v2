#!/usr/bin/env python3
"""Track active Harness sessions for concurrent VS Code operation."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

DB_PATH = REPO / "07_LOGS_AND_AUDIT" / "active_sessions.sqlite3"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS active_sessions (
            session_id TEXT PRIMARY KEY,
            invoked_by TEXT NOT NULL,
            branch TEXT NOT NULL,
            pid INTEGER NOT NULL,
            host TEXT NOT NULL,
            worktree_path TEXT NOT NULL DEFAULT '',
            lock_path TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(active_sessions)").fetchall()}
    if "worktree_path" not in cols:
        conn.execute("ALTER TABLE active_sessions ADD COLUMN worktree_path TEXT NOT NULL DEFAULT ''")
    if "lock_path" not in cols:
        conn.execute("ALTER TABLE active_sessions ADD COLUMN lock_path TEXT NOT NULL DEFAULT ''")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_active_sessions_updated_at ON active_sessions(updated_at)")
    conn.commit()
    return conn


def _git_branch() -> str:
    proc = run_safe(["git", "branch", "--show-current"], cwd=REPO, timeout=10)
    branch = (proc.stdout or "").strip()
    return branch or "unknown"


def _clean_argv(argv: list[str]) -> list[str]:
    # Ignore accidental placeholder args (for example ".") in Windows task wrappers.
    return [arg for arg in argv if arg.strip() != "."]


def cmd_start(
    invoked_by: str,
    session_id: str | None,
    worktree_path: str = "",
    lock_path: str = "",
) -> int:
    sid = (session_id or os.environ.get("CHROMATIC_SESSION_ID") or str(uuid.uuid4())).strip()
    now = _utc_now()
    row = {
        "session_id": sid,
        "invoked_by": invoked_by,
        "branch": _git_branch(),
        "pid": os.getpid(),
        "host": os.environ.get("COMPUTERNAME", "unknown"),
        "worktree_path": worktree_path,
        "lock_path": lock_path,
        "started_at": now,
        "updated_at": now,
    }
    conn = _ensure_db()
    try:
        conn.execute(
            """
            INSERT INTO active_sessions (session_id, invoked_by, branch, pid, host, started_at, updated_at)
            VALUES (:session_id, :invoked_by, :branch, :pid, :host, :started_at, :updated_at)
            ON CONFLICT(session_id) DO UPDATE SET
                invoked_by=excluded.invoked_by,
                branch=excluded.branch,
                pid=excluded.pid,
                host=excluded.host,
                worktree_path=CASE
                    WHEN excluded.worktree_path = '' THEN worktree_path
                    ELSE excluded.worktree_path
                END,
                lock_path=CASE
                    WHEN excluded.lock_path = '' THEN lock_path
                    ELSE excluded.lock_path
                END,
                updated_at=excluded.updated_at
            """,
            row,
        )
        conn.execute(
            """
            UPDATE active_sessions
            SET worktree_path = CASE
                    WHEN :worktree_path = '' THEN worktree_path
                    ELSE :worktree_path
                END,
                lock_path = CASE
                    WHEN :lock_path = '' THEN lock_path
                    ELSE :lock_path
                END
            WHERE session_id = :session_id
            """,
            row,
        )
        conn.commit()
    finally:
        conn.close()

    print(json.dumps({"ok": True, "session": row}, indent=2))
    return 0


def cmd_end(session_id: str) -> int:
    conn = _ensure_db()
    try:
        cur = conn.execute("DELETE FROM active_sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        removed = cur.rowcount
    finally:
        conn.close()

    print(json.dumps({"ok": True, "removed": removed, "session_id": session_id}, indent=2))
    return 0


def cmd_list() -> int:
    conn = _ensure_db()
    try:
        rows = conn.execute(
            """
            SELECT session_id, invoked_by, branch, pid, host, started_at, updated_at
                  , worktree_path, lock_path
            FROM active_sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()
    finally:
        conn.close()

    items = [
        {
            "session_id": r[0],
            "invoked_by": r[1],
            "branch": r[2],
            "pid": r[3],
            "host": r[4],
            "started_at": r[5],
            "updated_at": r[6],
            "worktree_path": r[7],
            "lock_path": r[8],
        }
        for r in rows
    ]
    print(json.dumps({"ok": True, "count": len(items), "items": items}, indent=2))
    return 0


def cmd_prune(older_than_minutes: int) -> int:
    cutoff = datetime.now(timezone.utc).timestamp() - older_than_minutes * 60
    conn = _ensure_db()
    try:
        rows = conn.execute("SELECT session_id, updated_at FROM active_sessions").fetchall()
        to_delete: list[str] = []
        for sid, updated_at in rows:
            try:
                ts = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00")).timestamp()
            except ValueError:
                to_delete.append(str(sid))
                continue
            if ts < cutoff:
                to_delete.append(str(sid))

        removed = 0
        if to_delete:
            cur = conn.executemany(
                "DELETE FROM active_sessions WHERE session_id = ?",
                [(sid,) for sid in to_delete],
            )
            removed = cur.rowcount
            conn.commit()
    finally:
        conn.close()

    print(
        json.dumps(
            {
                "ok": True,
                "removed": removed,
                "older_than_minutes": older_than_minutes,
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage active Harness sessions")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="Register/update active session")
    p_start.add_argument("--invoked-by", default="vscode")
    p_start.add_argument("--session-id")
    p_start.add_argument("--worktree-path", default="")
    p_start.add_argument("--lock-path", default="")

    p_end = sub.add_parser("end", help="Remove active session")
    p_end.add_argument("session_id")

    sub.add_parser("list", help="List active sessions")

    p_prune = sub.add_parser("prune", help="Remove stale sessions")
    p_prune.add_argument("--older-than-minutes", type=int, default=180)

    args = parser.parse_args(_clean_argv(list(argv if argv is not None else sys.argv[1:])))

    if args.cmd == "start":
        return cmd_start(
            invoked_by=args.invoked_by,
            session_id=args.session_id,
            worktree_path=args.worktree_path,
            lock_path=args.lock_path,
        )
    if args.cmd == "end":
        return cmd_end(session_id=args.session_id)
    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "prune":
        return cmd_prune(older_than_minutes=args.older_than_minutes)

    print(json.dumps({"ok": False, "error": f"unknown command: {args.cmd}"}, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
