"""Tests for unified intake queue contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intake.queue import (
    append_entry,
    list_queued,
    normalize_entry,
    validate_entry,
)

REPO = Path(__file__).resolve().parents[1]


def test_validate_goal_requires_goal_text():
    errors = validate_entry(
        {
            "id": "g1",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "t",
            "queued_at": "2026-05-29T00:00:00Z",
        }
    )
    assert any("goal" in e for e in errors)


def test_validate_bead_dispatch_ok():
    errors = validate_entry(
        {
            "id": "chromatic-harness-v2-nev",
            "source": "bead_hook",
            "kind": "bead_dispatch",
            "status": "queued",
            "title": "Route hook",
            "bead_id": "chromatic-harness-v2-nev",
            "queued_at": "2026-05-29T00:00:00Z",
        }
    )
    assert not errors


def test_append_and_list_queued(tmp_path: Path):
    q = tmp_path / "intake_queue.jsonl"
    append_entry(
        {
            "id": "test-goal-1",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "Test goal",
            "goal": "Do something atomic",
            "priority": "P1",
        },
        path=q,
    )
    queued = list_queued(path=q)
    assert len(queued) == 1
    assert queued[0].goal == "Do something atomic"


def test_dedupe_latest_status(tmp_path: Path):
    q = tmp_path / "intake_queue.jsonl"
    append_entry(
        {
            "id": "dup-1",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "First",
            "goal": "g",
        },
        path=q,
    )
    append_entry(
        {
            "id": "dup-1",
            "source": "manual",
            "kind": "goal",
            "status": "processed",
            "title": "First",
            "goal": "g",
        },
        path=q,
    )
    assert list_queued(path=q) == []


def test_schema_file_exists():
    schema = REPO / "01_PROTOCOLS" / "INTAKE" / "intake_queue.schema.json"
    assert schema.is_file()
    data = json.loads(schema.read_text(encoding="utf-8"))
    assert "queued" in data["properties"]["status"]["enum"]


def test_enqueue_follow_ups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import intake.queue as qmod

    q = tmp_path / "intake_queue.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    from intake.closure_feedback import enqueue_session_follow_ups

    ids = enqueue_session_follow_ups(
        ["Add E2E test", "-"],
        mission_id="CHR-TEST",
    )
    assert len(ids) == 1
    queued = list_queued(path=q)
    assert queued[0].kind == "follow_up"
    assert queued[0].source == "closure"
