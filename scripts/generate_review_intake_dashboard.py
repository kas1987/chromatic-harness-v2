#!/usr/bin/env python3
"""Generate a markdown dashboard from the review intake central collector DB."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

DEFAULT_DB = "07_LOGS_AND_AUDIT/review_intake/central_collector.sqlite3"


def generate_dashboard(db_path: Path, output: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total_findings = cur.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    total_queue = cur.execute("SELECT COUNT(*) FROM queue_items").fetchone()[0]
    ready = cur.execute("SELECT COUNT(*) FROM queue_items WHERE status='ready'").fetchone()[0]
    blocked = cur.execute("SELECT COUNT(*) FROM queue_items WHERE status='blocked'").fetchone()[0]
    needs_human = cur.execute("SELECT COUNT(*) FROM queue_items WHERE status='needs-human-decision'").fetchone()[0]

    by_type = cur.execute(
        "SELECT finding_type, COUNT(*) as c FROM findings GROUP BY finding_type ORDER BY c DESC"
    ).fetchall()

    by_agent = cur.execute(
        "SELECT owner_agent, COUNT(*) as c FROM queue_items WHERE status='ready' GROUP BY owner_agent ORDER BY c DESC"
    ).fetchall()

    recent = cur.execute(
        """SELECT finding_id, repo, pr_number, finding_type, confidence_score, status
           FROM findings ORDER BY ingested_at DESC LIMIT 20"""
    ).fetchall()

    conn.close()

    lines = [
        "# Chromatic Review Intake Dashboard",
        "",
        "## Summary",
        "",
        f"- **Total findings:** {total_findings}",
        f"- **Total queue items:** {total_queue}",
        f"- **Ready:** {ready}",
        f"- **Blocked:** {blocked}",
        f"- **Needs human decision:** {needs_human}",
        "",
        "## Findings by type",
        "",
        "| Type | Count |",
        "|---|---|",
    ]
    for row in by_type:
        lines.append(f"| {row['finding_type']} | {row['c']} |")

    lines.extend([
        "",
        "## Ready queue by agent",
        "",
        "| Agent | Count |",
        "|---|---|",
    ])
    for row in by_agent:
        lines.append(f"| {row['owner_agent']} | {row['c']} |")

    lines.extend([
        "",
        "## Recent findings",
        "",
        "| ID | Repo | PR | Type | Confidence | Status |",
        "|---|---|---|---|---|---|",
    ])
    for row in recent:
        lines.append(f"| {row['finding_id']} | {row['repo']} | {row['pr_number']} | {row['finding_type']} | {row['confidence_score']} | {row['status']} |")

    lines.append("")
    output.write_text("\n".join(lines))
    print(f"Dashboard written to {output}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--output", default="07_LOGS_AND_AUDIT/review_intake/dashboard.md")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    generate_dashboard(db_path, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
