#!/usr/bin/env python3
"""Append a session telemetry record to 05_REPORTS/telemetry.jsonl.

Usage:
  python scripts/hooks/append_session_telemetry.py [--session-id ID]
      [--beads-closed N] [--notes "text"]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TELEMETRY_FILE = REPO_ROOT / "05_REPORTS" / "telemetry.jsonl"
TODAY = "2026-05-31"


def git(*args) -> str:
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser(description="Append session telemetry record.")
    parser.add_argument("--session-id", default="", help="Optional session identifier")
    parser.add_argument(
        "--beads-closed",
        type=int,
        default=0,
        help="Number of beads closed this session",
    )
    parser.add_argument("--notes", default="", help="Free-text session notes")
    args = parser.parse_args()

    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    commit = git("log", "-1", "--format=%H") or "unknown"

    record: dict = {
        "date": TODAY,
        "branch": branch,
        "commit": commit,
        "beads_closed": args.beads_closed,
        "notes": args.notes,
    }
    if args.session_id:
        record["session_id"] = args.session_id

    TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TELEMETRY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    print(f"[telemetry] appended record to {TELEMETRY_FILE.relative_to(REPO_ROOT)}")
    print(
        f"  date={record['date']}  branch={branch}  commit={commit[:12]}  beads_closed={args.beads_closed}"
    )


if __name__ == "__main__":
    main()
