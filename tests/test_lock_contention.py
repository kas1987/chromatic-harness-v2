"""Tests for lock contention and stale-lock reclaim behavior."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def test_lock_contention_times_out(tmp_path, monkeypatch):
    import concurrency.session_lock as sl

    monkeypatch.setattr(sl, "LOCK_DB", tmp_path / "session_locks.sqlite3")
    metrics: list[dict[str, object]] = []

    def fake_emit(**kwargs):
        metrics.append(dict(kwargs))

    monkeypatch.setattr(sl, "_emit_lock_metric", fake_emit)

    owner = sl.acquire_lock("contention", session_id="s1", timeout_seconds=1.0)
    try:
        with pytest.raises(TimeoutError):
            sl.acquire_lock(
                "contention",
                session_id="s2",
                timeout_seconds=0.2,
                retry_interval_seconds=0.05,
            )
    finally:
        sl.release_lock("contention", owner)

    assert any(m.get("event_type") == "lock.acquire" for m in metrics)
    timeout_events = [m for m in metrics if m.get("event_type") == "lock.timeout"]
    assert timeout_events
    assert int(timeout_events[0].get("lock_wait_ms", 0)) >= 0
    assert int(timeout_events[0].get("attempts", 0)) >= 1


def test_stale_lock_reclaimed(tmp_path, monkeypatch):
    import concurrency.session_lock as sl

    monkeypatch.setattr(sl, "LOCK_DB", tmp_path / "session_locks.sqlite3")
    metrics: list[dict[str, object]] = []

    def fake_emit(**kwargs):
        metrics.append(dict(kwargs))

    monkeypatch.setattr(sl, "_emit_lock_metric", fake_emit)

    owner = sl.acquire_lock(
        "stale-reclaim",
        session_id="s1",
        timeout_seconds=1.0,
        lease_seconds=0,
    )
    assert owner.startswith("s1:")

    reclaimed = sl.acquire_lock(
        "stale-reclaim",
        session_id="s2",
        timeout_seconds=1.0,
        retry_interval_seconds=0.05,
    )
    try:
        assert reclaimed.startswith("s2:")
    finally:
        sl.release_lock("stale-reclaim", reclaimed)

    acquire_events = [m for m in metrics if m.get("event_type") == "lock.acquire"]
    assert len(acquire_events) >= 2
    assert all(int(m.get("lock_wait_ms", 0)) >= 0 for m in acquire_events)


def test_auto_intake_script_times_out_when_lock_held():
    import concurrency.session_lock as sl

    owner = sl.acquire_lock("intake_queue_mutation", session_id="holder", timeout_seconds=1.0)
    try:
        proc = subprocess.run(
            [
                PYTHON,
                str(REPO / "scripts" / "auto_intake.py"),
                "--dry-run",
                "--limit",
                "1",
                "--session-id",
                "contender",
                "--lock-timeout",
                "0.2",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    finally:
        sl.release_lock("intake_queue_mutation", owner)

    assert proc.returncode != 0
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert "timed out acquiring lock 'intake_queue_mutation'" in combined
