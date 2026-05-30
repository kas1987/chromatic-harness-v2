#!/usr/bin/env python3
"""Poll Chromatic Inbox Harness → repo intake_queue.jsonl.

Usage:
  python scripts/poll_inbox.py
  python scripts/poll_inbox.py --dry-run
  CHROMATIC_INBOX_ROOT=C:/chromatic-inbox-harness-data python scripts/poll_inbox.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from intake.inbox_adapter import poll_inbox_to_intake  # noqa: E402
from concurrency.session_lock import session_lock  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll inbox harness into intake queue")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--db", type=Path, default=None, help="Override sqlite path")
    parser.add_argument("--session-id", default="", help="Session id for lock ownership")
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for inbox polling lock",
    )
    args = parser.parse_args()

    session_id = args.session_id.strip() or "script-poll-inbox"
    with session_lock(
        "inbox_poll_mutation",
        session_id=session_id,
        timeout_seconds=args.lock_timeout,
    ):
        report = poll_inbox_to_intake(
            db_path=args.db,
            repo_root=REPO,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    print(json.dumps(report.to_dict(), indent=2))
    return 1 if report.errors and report.appended == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
