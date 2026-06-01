#!/usr/bin/env python3
"""find_event.py — locate an event (and its lifecycle history) by event_id.

Prints the most recent record by default. With ``--history`` prints every
record carrying the id (original + appended status updates) and a summary of
the latest status.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common_harness import repo_root

LOG_REL = "00_META/observability/ERROR_LOG.jsonl"


def find_records(log: Path, event_id: str) -> list[dict]:
    recs = []
    if not log.exists():
        return recs
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(rec, dict) and rec.get("event_id") == event_id:
            recs.append(rec)
    return recs


def main():
    ap = argparse.ArgumentParser(description="Locate an event by event_id.")
    ap.add_argument("--event-id", required=True)
    ap.add_argument("--repo-root")
    ap.add_argument("--history", action="store_true", help="Show all lifecycle records, not just the latest.")
    args = ap.parse_args()
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()

    recs = find_records(root / LOG_REL, args.event_id)
    if not recs:
        print(f"event not found: {args.event_id}", file=sys.stderr)
        return 2

    ordered = sorted(recs, key=lambda x: x.get("timestamp", ""))
    if args.history:
        print(json.dumps(ordered, indent=2))
        print(
            f"\n{len(ordered)} record(s); latest status: {ordered[-1].get('status')}",
            file=sys.stderr,
        )
    else:
        print(json.dumps(ordered[-1], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
