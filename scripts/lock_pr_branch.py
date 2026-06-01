#!/usr/bin/env python3
"""Acquire or release a file-based lock for a PR branch."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_LOCK_DIR = "07_LOGS_AND_AUDIT/review_intake/locks"


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def lock_path(lock_dir: Path, repo: str, pr_number: int) -> Path:
    safe_repo = repo.replace("/", "__")
    return lock_dir / f"{safe_repo}__pr{pr_number}.lock.json"


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
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_path(lock_dir, args.repo, args.pr_number)

    if args.command == "status":
        print(path.read_text() if path.exists() else "unlocked")
        return 0

    if args.command == "release":
        if path.exists():
            path.unlink()
            print("released")
        else:
            print("already unlocked")
        return 0

    if path.exists():
        data = json.loads(path.read_text())
        expires = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        if expires > now():
            print(json.dumps({"acquired": False, "reason": "active_lock", "lock": data}, indent=2))
            return 2

    started = now()
    data = {
        "lock_id": f"LOCK-{args.repo.replace('/', '-')}-PR{args.pr_number}",
        "repo": args.repo,
        "pr_number": args.pr_number,
        "branch": args.branch,
        "holder": args.holder,
        "queue_item_id": args.queue_item_id,
        "started_at": iso(started),
        "expires_at": iso(started + timedelta(minutes=args.ttl_minutes)),
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"acquired": True, "lock": data}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
