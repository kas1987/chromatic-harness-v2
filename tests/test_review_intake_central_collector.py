"""Tests for review_intake_central_collector.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from review_intake_central_collector import (  # noqa: E402
    dashboard_summary,
    init_db,
    ingest_findings,
    ingest_queue,
    read_jsonl,
)


class TestCentralCollector:
    def test_init_db_creates_tables(self, tmp_path: Path):
        db = tmp_path / "test.sqlite3"
        init_db(db)
        assert db.exists()

    def test_ingest_findings(self, tmp_path: Path):
        db = tmp_path / "test.sqlite3"
        init_db(db)
        findings = [
            {
                "finding_id": "RF-1",
                "source": "github_pr_review_comment",
                "repo": "owner/repo",
                "pr_number": 42,
                "body": "Fix this",
                "finding_type": "bug_fix",
                "risk_level": "medium",
                "status": "open",
                "dedupe_key": "dk1",
                "confidence_score": 80,
            }
        ]
        n = ingest_findings(db, findings)
        assert n == 1

    def test_ingest_findings_dedupe(self, tmp_path: Path):
        db = tmp_path / "test.sqlite3"
        init_db(db)
        findings = [
            {
                "finding_id": "RF-1",
                "source": "s",
                "repo": "r",
                "body": "b",
                "finding_type": "bug_fix",
                "risk_level": "low",
                "status": "open",
                "dedupe_key": "dk1",
                "confidence_score": 80,
            }
        ]
        ingest_findings(db, findings)
        n2 = ingest_findings(db, findings)
        assert n2 == 0

    def test_ingest_queue(self, tmp_path: Path):
        db = tmp_path / "test.sqlite3"
        init_db(db)
        queue_path = tmp_path / "queue.json"
        queue_path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "id": "NW-1",
                            "title": "T",
                            "status": "ready",
                            "priority": 80,
                            "repo": "r",
                            "area": "a",
                            "specialties": ["s"],
                            "owner_agent": "Sentinel",
                            "acceptance_checks": ["c"],
                            "links": ["l"],
                            "notes": "n",
                        }
                    ]
                }
            )
        )
        n = ingest_queue(db, queue_path)
        assert n == 1

    def test_dashboard_summary(self, tmp_path: Path):
        db = tmp_path / "test.sqlite3"
        init_db(db)
        ingest_findings(
            db,
            [
                {
                    "finding_id": "RF-1",
                    "source": "s",
                    "repo": "r",
                    "body": "b",
                    "finding_type": "bug_fix",
                    "risk_level": "low",
                    "status": "open",
                    "dedupe_key": "dk1",
                    "confidence_score": 80,
                }
            ],
        )
        summary = dashboard_summary(db)
        assert summary["total_findings"] == 1
        assert "generated_at" in summary
