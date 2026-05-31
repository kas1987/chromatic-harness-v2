#!/usr/bin/env python3
"""Append a session telemetry record to 05_REPORTS/telemetry.jsonl.

Usage:
  python scripts/hooks/append_session_telemetry.py [--session-id ID]
      [--beads-closed N] [--notes "text"]

When --beads-closed is omitted, the count is derived automatically by
querying ``bd list --status=closed --json`` and counting entries whose
updated_at falls within the last 4 hours (rough session window).
"""

import argparse
import json
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TELEMETRY_FILE = REPO_ROOT / "05_REPORTS" / "telemetry.jsonl"
_SESSION_WINDOW_HOURS = 4


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


def _find_bd() -> str | None:
    for name in ("bd.cmd", "bd.exe", "bd"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _derive_beads_closed() -> int:
    """Count beads closed within the last SESSION_WINDOW_HOURS hours via bd CLI.

    Returns 0 on any failure (fail-open — never blocks the hook).
    """
    bd = _find_bd()
    if bd is None:
        return 0
    try:
        result = subprocess.run(
            [bd, "list", "--status", "closed", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=15,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return 0
        rows = json.loads(result.stdout)
        if not isinstance(rows, list):
            return 0
        cutoff = datetime.now(timezone.utc).timestamp() - _SESSION_WINDOW_HOURS * 3600
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            updated = str(row.get("updated_at") or "").strip()
            if not updated:
                continue
            try:
                if updated.endswith("Z"):
                    ts = datetime.strptime(updated, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc
                    )
                else:
                    ts = datetime.fromisoformat(updated).astimezone(timezone.utc)
                if ts.timestamp() >= cutoff:
                    count += 1
            except Exception:
                continue
        return count
    except Exception:
        return 0


def main():
    parser = argparse.ArgumentParser(description="Append session telemetry record.")
    parser.add_argument("--session-id", default="", help="Optional session identifier")
    parser.add_argument(
        "--beads-closed",
        type=int,
        default=None,
        help=(
            "Number of beads closed this session. "
            "When omitted, derived automatically from bd (last 4h window)."
        ),
    )
    parser.add_argument("--notes", default="", help="Free-text session notes")
    args = parser.parse_args()

    if args.beads_closed is None:
        args.beads_closed = _derive_beads_closed()

    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    commit = git("log", "-1", "--format=%H") or "unknown"

    record: dict = {
        "date": date.today().isoformat(),
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
