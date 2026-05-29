"""Tests for inbox harness → intake queue adapter."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from intake.inbox_adapter import fetch_pending_items, poll_inbox_to_intake
from intake.queue import list_queued


def _seed_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE queue_items (
            id TEXT PRIMARY KEY,
            source TEXT,
            subject TEXT,
            body TEXT,
            priority TEXT,
            status TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO queue_items VALUES (?,?,?,?,?,?,?)",
        ("1", "github", "Fix intake", "Details here", "1", "pending", "2026-05-29T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO queue_items VALUES (?,?,?,?,?,?,?)",
        ("2", "gmail", "Done item", "", "2", "routed", "2026-05-29T00:00:00Z"),
    )
    conn.commit()
    conn.close()


def test_fetch_pending_only(tmp_path: Path):
    db = tmp_path / "chromatic_inbox.sqlite"
    _seed_db(db)
    items = fetch_pending_items(db)
    assert len(items) == 1
    assert items[0]["source"] == "inbox"
    assert "Fix intake" in items[0]["goal"]


def test_poll_appends_to_intake_queue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import intake.queue as qmod
    import intake.inbox_adapter as inbox_mod

    db = tmp_path / "db" / "chromatic_inbox.sqlite"
    db.parent.mkdir(parents=True)
    _seed_db(db)

    q = tmp_path / "intake_queue.jsonl"
    state = tmp_path / "sync.json"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)
    monkeypatch.setattr(inbox_mod, "default_queue_path", lambda repo_root=None: q)
    monkeypatch.setattr(inbox_mod, "SYNC_STATE", state)

    report = poll_inbox_to_intake(db_path=db, repo_root=tmp_path)
    assert report.appended == 1
    queued = list_queued(path=q)
    assert len(queued) == 1
    assert queued[0].context.get("inbox_id") == "1"


def test_poll_skips_duplicate_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import intake.inbox_adapter as inbox_mod

    db = tmp_path / "chromatic_inbox.sqlite"
    _seed_db(db)
    state = tmp_path / "sync.json"
    state.write_text(json.dumps({"synced_ids": ["1"]}), encoding="utf-8")
    monkeypatch.setattr(inbox_mod, "SYNC_STATE", state)

    report = poll_inbox_to_intake(db_path=db, repo_root=tmp_path)
    assert report.skipped >= 1
    assert report.appended == 0
