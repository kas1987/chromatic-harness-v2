#!/usr/bin/env python3
"""Generate a Chromatic review resolution comment and record (PDR S Phase 4 / AC6).

Resolution requires evidence: at least one changed file AND at least one validation
command. A ``Resolved`` status with no evidence is rejected so the queue can never be
closed on an unverified claim. The script prints the PR comment body and, unless
``--no-log``, appends a schema-valid ``review_resolution`` record to the resolution log.

  python scripts/post_review_resolution.py --finding RF-1 --task NW-1 --agent Sentinel \
    --status Resolved --files src/a.py --validation "pytest tests/test_a.py" | gh pr comment 42 --body-file -
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_LOG = "07_LOGS_AND_AUDIT/review_intake/resolution_log.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return f"{prefix}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12].upper()}"


def build_comment(args: argparse.Namespace, files: List[str], validation: List[str]) -> str:
    files_md = "\n".join(f"- `{f}`" for f in files)
    validation_md = "\n".join(f"- `{v}`" for v in validation)
    return f"""## Chromatic Review Resolution

**Finding:** {args.finding}
**Queue Item:** {args.task}
**Status:** {args.status}
**Agent:** {args.agent}
**Confidence:** {args.confidence}

### Change made
{args.change}

### Validation
{validation_md}

### Files changed
{files_md}

### Notes
Patch was kept scoped to the review finding and governed by Chromatic Review Intake rules.
"""


def build_record(args: argparse.Namespace, files: List[str], validation: List[str], links: List[str]) -> Dict[str, Any]:
    return {
        "resolution_id": stable_id("RR", args.finding, args.task, utc_now()),
        "finding_id": args.finding,
        "task_id": args.task,
        "agent": args.agent,
        "status": args.status,
        "confidence": args.confidence,
        "change": args.change,
        "files_changed": files,
        "validation": validation,
        "resolved_at": utc_now(),
        "links": links,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finding", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--status", default="Resolved", choices=["Resolved", "Blocked", "NeedsFollowUp"])
    parser.add_argument("--confidence", default="unknown")
    parser.add_argument("--change", default="Scoped review finding addressed.")
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--validation", nargs="*", default=[])
    parser.add_argument("--links", nargs="*", default=[])
    parser.add_argument("--log", default=DEFAULT_LOG)
    parser.add_argument(
        "--no-log", action="store_true", help="Print the comment only; do not append to the resolution log"
    )
    args = parser.parse_args()

    files = [f for f in args.files if f.strip()]
    validation = [v for v in args.validation if v.strip()]

    # AC6: a Resolved finding must carry evidence — changed files AND validation.
    if args.status == "Resolved" and (not files or not validation):
        missing = []
        if not files:
            missing.append("--files (at least one changed file)")
        if not validation:
            missing.append("--validation (at least one validation command/evidence)")
        print(
            "ERROR: Resolved status requires evidence. Missing: " + "; ".join(missing),
            file=sys.stderr,
        )
        return 2

    print(build_comment(args, files, validation))

    if not args.no_log:
        record = build_record(args, files, validation, [l for l in args.links if l.strip()])
        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
