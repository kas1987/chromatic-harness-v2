#!/usr/bin/env python3
"""update_event_status.py — append a status-update record for an existing event.

Append-only: the original event line is never mutated. A new ``status_update``
record is appended carrying the SAME ``event_id`` and a later timestamp, so
reports (which compute latest status per event_id) reflect the new status.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common_harness import (
    STATUSES,
    append_jsonl,
    repo_root,
    utc_now,
    validate_record,
)

LOG_REL = "00_META/observability/ERROR_LOG.jsonl"


def load_records(log: Path, event_id: str) -> list[dict]:
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
    ap = argparse.ArgumentParser(description="Append a status update for an event (append-only).")
    ap.add_argument("--event-id", required=True)
    ap.add_argument("--status", required=True)
    ap.add_argument("--linked-fix", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--repo-root")
    args = ap.parse_args()

    if args.status not in STATUSES:
        print(f"invalid status: {args.status} (allowed: {sorted(STATUSES)})", file=sys.stderr)
        return 2

    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    log = root / LOG_REL

    history = load_records(log, args.event_id)
    if not history:
        print(f"event not found: {args.event_id}", file=sys.stderr)
        return 2

    # Carry forward identifying context from the most recent record.
    latest = sorted(history, key=lambda x: x.get("timestamp", ""))[-1]
    prev_status = latest.get("status")

    record = {
        "event_id": args.event_id,  # SAME id -> reports group lifecycle together
        "timestamp": utc_now(),
        "repo": latest.get("repo", root.name),
        "workspace": latest.get("workspace", str(root)),
        "source": latest.get("source", {"surface": "manual"}),
        "event_type": "status_update",
        "severity": "info",
        "category": "manual_note",
        "status": args.status,
        "previous_status": prev_status,
        "updates_event": args.event_id,
        "raw_excerpt": args.note or f"Status update for {args.event_id}: {prev_status} -> {args.status}",
        "linked_fix": args.linked_fix or None,
    }

    errs = validate_record(record)
    if errs:
        print("Unable to log invalid status update: " + str(errs), file=sys.stderr)
        return 1

    append_jsonl(log, record)
    print(f"status updated: {args.event_id} {prev_status} -> {args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
