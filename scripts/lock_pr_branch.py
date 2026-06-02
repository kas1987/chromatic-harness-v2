#!/usr/bin/env python3
"""Acquire or release a file-based lock for a PR branch.

Enforces the PDR collision rule (S10): one PR branch gets one active mutating
agent. Locks expire after a TTL; stale locks can be force-released by the
orchestrator. The acquire/release/status helpers are importable so the queue
dispatcher can hold a lock for the lifetime of a mutation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

DEFAULT_LOCK_DIR = "07_LOGS_AND_AUDIT/review_intake/locks"


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def lock_path(lock_dir: Path, repo: str, pr_number: int) -> Path:
    safe_repo = repo.replace("/", "__")
    return lock_dir / f"{safe_repo}__pr{pr_number}.lock.json"


def read_lock(path: Path) -> Dict[str, Any] | None:
    if not path.exists() or not path.read_text().strip():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def is_active(lock: Dict[str, Any], at: datetime | None = None) -> bool:
    at = at or now()
    try:
        expires = datetime.fromisoformat(str(lock["expires_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return False
    return expires > at


def acquire(
    lock_dir: Path,
    repo: str,
    pr_number: int,
    branch: str = "unknown",
    holder: str = "unknown-agent",
    queue_item_id: str = "unknown-task",
    ttl_minutes: int = 30,
) -> Tuple[bool, Dict[str, Any]]:
    """Acquire a PR branch lock. Returns (acquired, payload).

    payload is the lock record on success, or ``{"acquired": False, ...}`` when a
    non-expired lock is already held by someone else.
    """
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_path(lock_dir, repo, pr_number)
    existing = read_lock(path)
    if existing and is_active(existing):
        return False, {"acquired": False, "reason": "active_lock", "lock": existing}

    started = now()
    data = {
        "lock_id": f"LOCK-{repo.replace('/', '-')}-PR{pr_number}",
        "repo": repo,
        "pr_number": pr_number,
        "branch": branch,
        "holder": holder,
        "queue_item_id": queue_item_id,
        "started_at": iso(started),
        "expires_at": iso(started + timedelta(minutes=ttl_minutes)),
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return True, data


def release(lock_dir: Path, repo: str, pr_number: int) -> bool:
    path = lock_path(lock_dir, repo, pr_number)
    if path.exists():
        path.unlink()
        return True
    return False


def status(lock_dir: Path, repo: str, pr_number: int) -> Dict[str, Any] | None:
    return read_lock(lock_path(lock_dir, repo, pr_number))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["acquire", "release", "status"])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--branch", default="unknown")
    parser.add_argument("--holder", default="unknown-agent")
    parser.add_argument("--queue-item-id", default="unknown-task")
    parser.add_argument("--ttl-minutes", type=int, default=30)
    parser.add_argument("--lock-dir", default=DEFAULT_LOCK_DIR)
    args = parser.parse_args()

    lock_dir = Path(args.lock_dir)

    if args.command == "status":
        current = status(lock_dir, args.repo, args.pr_number)
        print(json.dumps(current, indent=2, sort_keys=True) if current else "unlocked")
        return 0

    if args.command == "release":
        print("released" if release(lock_dir, args.repo, args.pr_number) else "already unlocked")
        return 0

    acquired, payload = acquire(
        lock_dir,
        args.repo,
        args.pr_number,
        branch=args.branch,
        holder=args.holder,
        queue_item_id=args.queue_item_id,
        ttl_minutes=args.ttl_minutes,
    )
    if acquired:
        print(json.dumps({"acquired": True, "lock": payload}, indent=2))
        return 0
    print(json.dumps(payload, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
