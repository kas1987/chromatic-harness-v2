#!/usr/bin/env python3
"""Central collector for Chromatic review findings across multiple repos.

Aggregates review findings from per-repo JSONL files into a SQLite database
and provides a simple dashboard query interface.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_DB = "07_LOGS_AND_AUDIT/review_intake/central_collector.sqlite3"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            finding_id TEXT PRIMARY KEY,
            source TEXT,
            repo TEXT,
            pr_number INTEGER,
            review_id TEXT,
            comment_id TEXT,
            author TEXT,
            created_at TEXT,
            commit_sha TEXT,
            path TEXT,
            line INTEGER,
            body TEXT,
            finding_type TEXT,
            severity TEXT,
            risk_level TEXT,
            status TEXT,
            dedupe_key TEXT UNIQUE,
            suggested_agent TEXT,
            confidence_score INTEGER,
            acceptance_checks TEXT,
            links TEXT,
            ingested_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS queue_items (
            id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            priority INTEGER,
            repo TEXT,
            area TEXT,
            specialties TEXT,
            owner_agent TEXT,
            depends_on TEXT,
            blocked_by TEXT,
            risk_level TEXT,
            confidence_score INTEGER,
            acceptance_checks TEXT,
            links TEXT,
            notes TEXT,
            source_finding_id TEXT,
            allowed_files TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviewer_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo TEXT,
            finding_type TEXT,
            pattern TEXT,
            count INTEGER DEFAULT 1,
            first_seen TEXT,
            last_seen TEXT
        )
    """)
    conn.commit()
    conn.close()


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def ingest_findings(db_path: Path, findings: List[Dict[str, Any]]) -> int:
    conn = sqlite3.connect(str(db_path))
    inserted = 0
    for f in findings:
        try:
            conn.execute(
                """
                INSERT INTO findings (
                    finding_id, source, repo, pr_number, review_id, comment_id,
                    author, created_at, commit_sha, path, line, body,
                    finding_type, severity, risk_level, status, dedupe_key,
                    suggested_agent, confidence_score, acceptance_checks, links, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f.get("finding_id"),
                    f.get("source"),
                    f.get("repo"),
                    f.get("pr_number"),
                    str(f.get("review_id")) if f.get("review_id") is not None else None,
                    str(f.get("comment_id")) if f.get("comment_id") is not None else None,
                    f.get("author"),
                    f.get("created_at"),
                    f.get("commit_sha"),
                    f.get("path"),
                    f.get("line"),
                    f.get("body"),
                    f.get("finding_type"),
                    f.get("severity"),
                    f.get("risk_level"),
                    f.get("status"),
                    f.get("dedupe_key"),
                    f.get("suggested_agent"),
                    f.get("confidence_score"),
                    json.dumps(f.get("acceptance_checks", [])),
                    json.dumps(f.get("links", {})),
                    now(),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return inserted


def ingest_queue(db_path: Path, queue_path: Path) -> int:
    if not queue_path.exists():
        return 0
    data = json.loads(queue_path.read_text())
    items = data.get("items", [])
    conn = sqlite3.connect(str(db_path))
    inserted = 0
    for item in items:
        try:
            conn.execute(
                """
                INSERT INTO queue_items (
                    id, title, status, priority, repo, area, specialties,
                    owner_agent, depends_on, blocked_by, risk_level, confidence_score,
                    acceptance_checks, links, notes, source_finding_id, allowed_files,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("id"),
                    item.get("title"),
                    item.get("status"),
                    item.get("priority"),
                    item.get("repo"),
                    item.get("area"),
                    json.dumps(item.get("specialties", [])),
                    item.get("owner_agent"),
                    json.dumps(item.get("depends_on", [])),
                    json.dumps(item.get("blocked_by", [])),
                    item.get("risk_level"),
                    item.get("confidence_score"),
                    json.dumps(item.get("acceptance_checks", [])),
                    json.dumps(item.get("links", [])),
                    item.get("notes"),
                    item.get("source_finding_id"),
                    json.dumps(item.get("allowed_files", [])),
                    item.get("created_at"),
                    item.get("updated_at"),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            conn.execute(
                """
                UPDATE queue_items SET
                    title=?, status=?, priority=?, repo=?, area=?,
                    specialties=?, owner_agent=?, depends_on=?, blocked_by=?,
                    risk_level=?, confidence_score=?, acceptance_checks=?, links=?,
                    notes=?, source_finding_id=?, allowed_files=?, updated_at=?
                WHERE id=?
                """,
                (
                    item.get("title"),
                    item.get("status"),
                    item.get("priority"),
                    item.get("repo"),
                    item.get("area"),
                    json.dumps(item.get("specialties", [])),
                    item.get("owner_agent"),
                    json.dumps(item.get("depends_on", [])),
                    json.dumps(item.get("blocked_by", [])),
                    item.get("risk_level"),
                    item.get("confidence_score"),
                    json.dumps(item.get("acceptance_checks", [])),
                    json.dumps(item.get("links", [])),
                    item.get("notes"),
                    item.get("source_finding_id"),
                    json.dumps(item.get("allowed_files", [])),
                    item.get("updated_at") or now(),
                    item.get("id"),
                ),
            )
    conn.commit()
    conn.close()
    return inserted


def dashboard_summary(db_path: Path) -> Dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total_findings = cur.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    total_queue = cur.execute("SELECT COUNT(*) FROM queue_items").fetchone()[0]
    ready_queue = cur.execute("SELECT COUNT(*) FROM queue_items WHERE status='ready'").fetchone()[0]
    by_type = cur.execute(
        "SELECT finding_type, COUNT(*) as c FROM findings GROUP BY finding_type ORDER BY c DESC"
    ).fetchall()
    by_agent = cur.execute(
        "SELECT owner_agent, COUNT(*) as c FROM queue_items WHERE status='ready' GROUP BY owner_agent ORDER BY c DESC"
    ).fetchall()
    recent = cur.execute(
        "SELECT finding_id, repo, pr_number, finding_type, confidence_score, status FROM findings ORDER BY ingested_at DESC LIMIT 10"
    ).fetchall()

    conn.close()

    return {
        "total_findings": total_findings,
        "total_queue_items": total_queue,
        "ready_queue_items": ready_queue,
        "by_finding_type": [{"type": r["finding_type"], "count": r["c"]} for r in by_type],
        "by_agent": [{"agent": r["owner_agent"], "count": r["c"]} for r in by_agent],
        "recent_findings": [dict(r) for r in recent],
        "generated_at": now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--findings", help="Path to findings JSONL to ingest")
    parser.add_argument("--queue", help="Path to queue JSON to ingest")
    parser.add_argument("--dashboard", action="store_true", help="Print dashboard summary")
    parser.add_argument("--init", action="store_true", help="Initialize SQLite schema")
    args = parser.parse_args()

    db_path = Path(args.db)

    if args.init:
        init_db(db_path)
        print(f"Initialized {db_path}")
        return 0

    if not db_path.exists():
        init_db(db_path)

    if args.findings:
        findings = read_jsonl(Path(args.findings))
        n = ingest_findings(db_path, findings)
        print(f"Ingested {n} findings")

    if args.queue:
        n = ingest_queue(db_path, Path(args.queue))
        print(f"Ingested/updated {n} queue items")

    if args.dashboard:
        summary = dashboard_summary(db_path)
        print(json.dumps(summary, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
