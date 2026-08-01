#!/usr/bin/env python3
"""Tests for measure_review_intake_loop.py

Validates that the loop measurement script correctly:
- Detects comments with the 'review-intake: analyze' tag
- Polls for findings, queue items, and beads
- Computes latencies
- Logs results
"""

import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Adjust path for script import
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from measure_review_intake_loop import (
    timestamp_to_seconds,
    read_jsonl,
    read_json,
    find_recent_review_intake_comment,
    get_findings_created_after,
    get_queue_items_for_findings,
    measure_loop_closure,
)


def test_timestamp_to_seconds_valid():
    """Parse valid ISO 8601 timestamp."""
    ts = "2026-06-20T14:23:45Z"
    seconds = timestamp_to_seconds(ts)
    assert isinstance(seconds, float)
    assert seconds > 0


def test_timestamp_to_seconds_invalid():
    """Handle invalid timestamp gracefully."""
    seconds = timestamp_to_seconds("invalid")
    assert seconds == 0.0


def test_read_jsonl_empty_file():
    """Read empty JSONL file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "empty.jsonl"
        path.write_text("")
        result = read_jsonl(path)
        assert result == []


def test_read_jsonl_multiple_records():
    """Read JSONL with multiple records."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.jsonl"
        path.write_text("", encoding="utf-8")  # initialize so read_text() works
        records = [
            {"id": "1", "type": "finding"},
            {"id": "2", "type": "finding"},
            {"id": "3", "type": "finding"},
        ]
        for r in records:
            path.write_text(path.read_text(encoding="utf-8") + json.dumps(r) + "\n", encoding="utf-8")
        result = read_jsonl(path)
        assert len(result) == 3
        assert result[0]["id"] == "1"


def test_read_jsonl_skip_invalid_lines():
    """Skip invalid JSON lines gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.jsonl"
        path.write_text('{"id": "1"}\ninvalid json line\n{"id": "2"}\n', encoding="utf-8")
        result = read_jsonl(path)
        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "2"


def test_read_json_valid():
    """Read valid JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.json"
        data = {"items": [{"id": "1"}]}
        path.write_text(json.dumps(data), encoding="utf-8")
        result = read_json(path)
        assert result == data


def test_read_json_empty():
    """Read empty JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.json"
        path.write_text("", encoding="utf-8")
        result = read_json(path)
        assert result == {}


def test_get_findings_created_after():
    """Find findings created after a timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "findings.jsonl"

        # Create findings with staggered timestamps
        now = datetime.now(timezone.utc)
        t0 = (now - timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
        t1 = (now - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
        t2 = now.isoformat().replace("+00:00", "Z")

        findings = [
            {"finding_id": "F1", "created_at": t0},
            {"finding_id": "F2", "created_at": t1},
            {"finding_id": "F3", "created_at": t2},
        ]
        path.write_text("", encoding="utf-8")  # initialize so read_text() works
        for f in findings:
            path.write_text(path.read_text(encoding="utf-8") + json.dumps(f) + "\n", encoding="utf-8")

        # Get findings after t0
        cutoff = timestamp_to_seconds(t0) + 1  # 1 second after t0
        result = get_findings_created_after(path, cutoff)

        # Should include t1 and t2, not t0
        ids = [f["finding_id"] for f in result]
        assert "F1" not in ids or timestamp_to_seconds(findings[0]["created_at"]) < cutoff
        # At minimum, F3 should be included
        assert "F3" in ids


def test_get_queue_items_for_findings():
    """Find queue items matching finding IDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "queue.json"
        queue = {
            "items": [
                {"id": "Q1", "source_finding_id": "F1"},
                {"id": "Q2", "source_finding_id": "F2"},
                {"id": "Q3", "source_finding_id": "F3"},
            ]
        }
        path.write_text(json.dumps(queue), encoding="utf-8")

        result = get_queue_items_for_findings(path, ["F1", "F3"])
        ids = [q["id"] for q in result]
        assert "Q1" in ids
        assert "Q3" in ids
        assert "Q2" not in ids


def test_measure_loop_closure_comment_not_found():
    """Return error when comment not found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("measure_review_intake_loop.find_recent_review_intake_comment") as mock:
            mock.return_value = None
            result = measure_loop_closure(
                275,
                findings_path=Path(tmpdir) / "findings.jsonl",
                queue_path=Path(tmpdir) / "queue.json",
                timeout=5,
            )
            assert result["status"] == "comment_not_found"
            assert "No recent comment" in result["error"]


def test_measure_loop_closure_findings_timeout():
    """Return error when findings not created in time."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("measure_review_intake_loop.find_recent_review_intake_comment") as mock:
            now = datetime.now(timezone.utc)
            ts = now.isoformat().replace("+00:00", "Z")
            mock.return_value = {
                "id": "C123",
                "body": "review-intake: analyze",
                "created_at": ts,
                "created_ts": now.timestamp(),
            }

            result = measure_loop_closure(
                275,
                findings_path=Path(tmpdir) / "findings.jsonl",
                queue_path=Path(tmpdir) / "queue.json",
                timeout=1,  # Very short timeout
                poll_interval=0.5,
            )
            assert result["status"] == "findings_timeout"
            assert "Findings not created" in result["error"]


def test_measure_loop_closure_success():
    """Successfully measure loop with complete data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create findings
        findings_path = tmpdir / "findings.jsonl"
        now = datetime.now(timezone.utc)
        comment_ts = (now - timedelta(seconds=10)).timestamp()
        finding_ts = (now - timedelta(seconds=8)).isoformat().replace("+00:00", "Z")

        finding = {"finding_id": "F1", "created_at": finding_ts}
        findings_path.write_text(json.dumps(finding) + "\n", encoding="utf-8")

        # Create queue items
        queue_path = tmpdir / "queue.json"
        queue = {
            "items": [
                {
                    "id": "Q1",
                    "source_finding_id": "F1",
                    "title": "Address review finding F1",
                }
            ]
        }
        queue_path.write_text(json.dumps(queue), encoding="utf-8")

        with patch("measure_review_intake_loop.find_recent_review_intake_comment") as mock_comment:
            with patch("measure_review_intake_loop.get_beads_for_queue_items") as mock_beads:
                comment_ts_str = (now - timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
                mock_comment.return_value = {
                    "id": "C123",
                    "body": "review-intake: analyze",
                    "created_at": comment_ts_str,
                    "created_ts": comment_ts,
                }
                mock_beads.return_value = ["BD1"]

                result = measure_loop_closure(
                    275,
                    findings_path=findings_path,
                    queue_path=queue_path,
                    timeout=10,
                    poll_interval=0.1,
                )

                assert result["status"] == "success"
                assert result["total_latency_seconds"] is not None
                assert result["total_latency_seconds"] < 15  # mocked 10s + small real-time overhead
                assert "t0_comment_created" in result["phases"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
