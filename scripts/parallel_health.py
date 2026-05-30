#!/usr/bin/env python3
"""Report concurrent Harness health: sessions, locks, and worktrees."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SESSIONS_DB = REPO / "07_LOGS_AND_AUDIT" / "active_sessions.sqlite3"
LOCKS_DB = REPO / ".agents" / "locks" / "session_locks.sqlite3"
WORKTREES_DIR = REPO / ".worktrees"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _list_sessions() -> list[dict[str, Any]]:
    if not SESSIONS_DB.is_file():
        return []
    conn = sqlite3.connect(SESSIONS_DB)
    try:
        rows = conn.execute(
            """
            SELECT session_id, invoked_by, branch, pid, host, started_at, updated_at,
                   COALESCE(worktree_path, ''), COALESCE(lock_path, '')
            FROM active_sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()
    finally:
        conn.close()

    return [
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


def _list_locks() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not LOCKS_DB.is_file():
        return [], []
    conn = sqlite3.connect(LOCKS_DB)
    try:
        rows = conn.execute(
            """
            SELECT lock_name, owner_session_id, owner_token, acquired_at, expires_at
            FROM session_locks
            ORDER BY acquired_at DESC
            """
        ).fetchall()
    finally:
        conn.close()

    active: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    now = _now()
    for row in rows:
        item = {
            "lock_name": row[0],
            "owner_session_id": row[1],
            "owner_token": row[2],
            "acquired_at": row[3],
            "expires_at": row[4],
        }
        expires = _parse_iso(str(row[4]))
        if expires is not None and expires <= now:
            stale.append(item)
        else:
            active.append(item)
    return active, stale


def _git_worktrees() -> list[str]:
    proc = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        return []

    paths: list[str] = []
    for line in (proc.stdout or "").splitlines():
        if line.startswith("worktree "):
            paths.append(line.split(" ", 1)[1])
    return paths


def _declared_worktrees() -> list[str]:
    if not WORKTREES_DIR.is_dir():
        return []
    return sorted(str(p.resolve()) for p in WORKTREES_DIR.iterdir() if p.is_dir())


def _prune_stale_locks(stale_locks: list[dict[str, Any]]) -> int:
    if not stale_locks or not LOCKS_DB.is_file():
        return 0
    conn = sqlite3.connect(LOCKS_DB)
    removed = 0
    try:
        for item in stale_locks:
            lock_name = str(item.get("lock_name", ""))
            owner_token = str(item.get("owner_token", ""))
            if not lock_name or not owner_token:
                continue
            cur = conn.execute(
                "DELETE FROM session_locks WHERE lock_name = ? AND owner_token = ?",
                (lock_name, owner_token),
            )
            removed += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return removed


def _prune_orphaned_worktrees(orphaned_worktrees: list[str]) -> tuple[int, list[str]]:
    removed = 0
    errors: list[str] = []
    for path in orphaned_worktrees:
        try:
            resolved = Path(path).resolve()
        except OSError:
            errors.append(f"invalid path: {path}")
            continue
        # Safety guard: only prune dedicated parallel worktree directory.
        if WORKTREES_DIR.resolve() not in resolved.parents:
            errors.append(f"refused (outside .worktrees): {path}")
            continue
        proc = subprocess.run(
            ["git", "worktree", "remove", "--force", str(resolved)],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode == 0:
            removed += 1
        else:
            err = (proc.stderr or proc.stdout or "git worktree remove failed").strip()
            errors.append(f"{path}: {err[-300:]}")
    return removed, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Parallel session health report")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Prune stale locks and orphaned worktrees",
    )
    args = parser.parse_args()

    sessions = _list_sessions()
    active_locks, stale_locks = _list_locks()
    git_worktrees = _git_worktrees()
    declared_worktrees = _declared_worktrees()

    active_worktree_paths = {
        str(Path(item.get("worktree_path", "")).resolve())
        for item in sessions
        if item.get("worktree_path")
    }
    orphaned_worktrees = sorted(
        path for path in declared_worktrees if path not in active_worktree_paths
    )

    pruned_locks = 0
    pruned_worktrees = 0
    prune_errors: list[str] = []
    if args.prune:
        pruned_locks = _prune_stale_locks(stale_locks)
        pruned_worktrees, prune_errors = _prune_orphaned_worktrees(orphaned_worktrees)
        active_locks, stale_locks = _list_locks()
        declared_worktrees = _declared_worktrees()
        git_worktrees = _git_worktrees()
        orphaned_worktrees = sorted(
            path for path in declared_worktrees if path not in active_worktree_paths
        )

    out = {
        "ok": True,
        "summary": {
            "active_sessions": len(sessions),
            "active_locks": len(active_locks),
            "stale_locks": len(stale_locks),
            "declared_worktrees": len(declared_worktrees),
            "git_worktrees": len(git_worktrees),
            "orphaned_worktrees": len(orphaned_worktrees),
        },
        "prune": {
            "enabled": args.prune,
            "pruned_stale_locks": pruned_locks,
            "pruned_orphaned_worktrees": pruned_worktrees,
            "errors": prune_errors,
        },
        "active_sessions": sessions,
        "active_locks": active_locks,
        "stale_locks": stale_locks,
        "orphaned_worktrees": orphaned_worktrees,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
