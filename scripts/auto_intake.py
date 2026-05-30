#!/usr/bin/env python3
"""Drain intake_queue.jsonl into beads.

Usage:
  python scripts/auto_intake.py              # process all queued (live)
  python scripts/auto_intake.py --dry-run    # simulate without bd
  python scripts/auto_intake.py --limit 3
  python scripts/auto_intake.py --no-claim   # create only, do not claim
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

from intake.auto_intake import drain_queue  # noqa: E402
from concurrency.session_lock import session_lock  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Drain intake queue to beads")
    parser.add_argument("--dry-run", action="store_true", help="Do not call bd")
    parser.add_argument("--limit", type=int, default=None, help="Max entries to process")
    parser.add_argument("--no-claim", action="store_true", help="Skip bd update --claim")
    parser.add_argument("--session-id", default="", help="Session id for lock ownership")
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for intake queue lock",
    )
    args = parser.parse_args()

    session_id = args.session_id.strip() or "script-auto-intake"
    with session_lock(
        "intake_queue_mutation",
        session_id=session_id,
        timeout_seconds=args.lock_timeout,
    ):
        report = drain_queue(
            repo_root=REPO,
            limit=args.limit,
            dry_run=args.dry_run,
            claim=not args.no_claim,
        )
    print(json.dumps(report.to_dict(), indent=2))
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
