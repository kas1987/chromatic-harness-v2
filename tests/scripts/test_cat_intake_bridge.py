"""Tests for cat_intake_bridge.py

Covers PR #277 Phase 3 fixes:
- default intake queue path is repo-relative
- malformed JSONL rows are skipped
- already-bridged ids are not reprocessed
- processed-id persistence
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import cat_intake_bridge as bridge


def test_read_intake_queue_default_path_is_repo_relative():
    """When path is omitted, the queue resolves to repo-root relative."""
    default = bridge.read_intake_queue()
    assert isinstance(default, list)
    repo_root = Path(bridge.__file__).resolve().parents[1]
    expected = repo_root / "07_LOGS_AND_AUDIT" / "intake_queue.jsonl"
    assert expected.as_posix().endswith("07_LOGS_AND_AUDIT/intake_queue.jsonl")


def test_read_intake_queue_skips_malformed_rows():
    """A malformed JSONL row must not crash the bridge."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q = Path(tmpdir) / "queue.jsonl"
        q.write_text(
            json.dumps({"id": "1", "title": "good"}) + "\n"
            "this is not json\n" + json.dumps({"id": "2", "title": "also good"}) + "\n",
            encoding="utf-8",
        )
        entries = bridge.read_intake_queue(q)
        ids = [e["id"] for e in entries]
        assert ids == ["1", "2"]


def test_read_intake_queue_skips_already_processed():
    """Entries whose ids were already bridged must be skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q = Path(tmpdir) / "queue.jsonl"
        q.write_text(
            json.dumps({"id": "a", "title": "first"}) + "\n" + json.dumps({"id": "a", "title": "duplicate"}) + "\n",
            encoding="utf-8",
        )
        first = bridge.read_intake_queue(q)
        assert [e["id"] for e in first] == ["a"]
        second = bridge.read_intake_queue(q)
        assert second == []


def test_read_intake_queue_returns_empty_when_missing():
    """Missing queue file should yield an empty list, not crash."""
    missing = Path("/nonexistent/path/queue.jsonl")
    assert bridge.read_intake_queue(missing) == []


def test_processed_ids_persistence_round_trip():
    """Processed ids are saved and loaded across calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q = Path(tmpdir) / "queue.jsonl"
        q.write_text(json.dumps({"id": "x"}) + "\n", encoding="utf-8")
        bridge.read_intake_queue(q)
        pid_path = bridge._processed_ids_path(q)
        assert pid_path.exists()
        assert json.loads(pid_path.read_text(encoding="utf-8")) == ["x"]


def test_read_intake_queue_skips_entries_without_id():
    """Rows without an id are ignored so they cannot pollute the bridge."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q = Path(tmpdir) / "queue.jsonl"
        q.write_text(
            json.dumps({"title": "no id"}) + "\n" + json.dumps({"id": "y"}) + "\n",
            encoding="utf-8",
        )
        entries = bridge.read_intake_queue(q)
        assert [e["id"] for e in entries] == ["y"]
