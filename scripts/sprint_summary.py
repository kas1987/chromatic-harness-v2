#!/usr/bin/env python3
"""sprint_summary.py — reads 05_REPORTS/telemetry.jsonl and prints a sprint summary."""

import json
import sys
from pathlib import Path


def load_telemetry(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        print(f"[WARN] telemetry file not found: {path}", file=sys.stderr)
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"[WARN] skipping malformed line: {exc}", file=sys.stderr)
    return records


def summarize(records: list[dict]) -> str:
    if not records:
        return "No telemetry records found."

    total_beads = sum(r.get("beads_closed", 0) for r in records)
    dates = sorted(r["date"] for r in records if "date" in r)
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "unknown"
    last = sorted(records, key=lambda r: r.get("date", ""), reverse=True)[0]

    lines = [
        "## Sprint Summary",
        "",
        f"- **Sessions logged:** {len(records)}",
        f"- **Total beads closed:** {total_beads}",
        f"- **Date range:** {date_range}",
        f"- **Last session date:** {last.get('date', 'N/A')}",
        f"- **Last session branch:** {last.get('branch', 'N/A')}",
        f"- **Last session notes:** {last.get('notes', 'N/A')}",
        "",
        "### Per-session breakdown",
        "",
        "| Date | Branch | Beads Closed | Notes |",
        "|------|--------|-------------|-------|",
    ]
    for r in sorted(records, key=lambda r: r.get("date", "")):
        lines.append(
            f"| {r.get('date', '?')} "
            f"| {r.get('branch', '?')} "
            f"| {r.get('beads_closed', 0)} "
            f"| {r.get('notes', '—')} |"
        )

    return "\n".join(lines)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    telemetry_path = repo_root / "05_REPORTS" / "telemetry.jsonl"
    records = load_telemetry(telemetry_path)
    print(summarize(records))


if __name__ == "__main__":
    main()
