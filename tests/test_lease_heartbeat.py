"""Tests for lease_heartbeat.py (P1-CC-006 / ju0o.6). Network-free, tmp-isolated."""

from __future__ import annotations

import importlib.util
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _lm():
    return _load("lease_manager", "scripts/lease_manager.py")


def _seed(ledger: Path, lease_id: str, heartbeat_dt: datetime, *, expiry_hours: int = 1) -> None:
    lm = _lm()
    expires = (datetime.now(timezone.utc) + timedelta(hours=expiry_hours)).isoformat().replace("+00:00", "Z")
    record = {
        "lease_id": lease_id,
        "task_id": "T-test",
        "owner_agent": "AgentA",
        "resources": ["scripts/foo.py"],
        "mode": "write",
        "risk_tier": "T2",
        "status": "active",
        "created_at": heartbeat_dt.isoformat().replace("+00:00", "Z"),
        "expires_at": expires,
        "heartbeat_at": heartbeat_dt.isoformat().replace("+00:00", "Z"),
        "rollback_plan": "none",
        "metadata": {},
    }
    records = lm.load_ledger(ledger)
    records.append(record)
    lm.write_ledger(ledger, records)


def test_heartbeat_updates_lease(tmp_path):
    mod = _load("lease_heartbeat", "scripts/lease_heartbeat.py")
    ledger = tmp_path / "l.jsonl"
    _seed(ledger, "lease-1", datetime.now(timezone.utc) - timedelta(minutes=30))
    res = mod.record_heartbeat("lease-1", ledger, extend_minutes=120)
    assert res["status"] == "renewed"
    # heartbeat_at moved forward to ~now
    lm = _lm()
    rec = lm.load_ledger(ledger)[0]
    hb = datetime.fromisoformat(rec["heartbeat_at"].replace("Z", "+00:00"))
    assert (datetime.now(timezone.utc) - hb).total_seconds() < 60


def test_heartbeat_not_found(tmp_path):
    mod = _load("lease_heartbeat", "scripts/lease_heartbeat.py")
    res = mod.record_heartbeat("missing", tmp_path / "l.jsonl")
    assert res["status"] == "not_found"


def test_missed_heartbeats_detected(tmp_path):
    mod = _load("lease_heartbeat", "scripts/lease_heartbeat.py")
    ledger = tmp_path / "l.jsonl"
    _seed(ledger, "lease-stale", datetime.now(timezone.utc) - timedelta(minutes=60))
    missed = mod.find_missed(ledger, grace_minutes=15)
    assert [m["lease_id"] for m in missed] == ["lease-stale"]


def test_recent_heartbeat_not_missed(tmp_path):
    mod = _load("lease_heartbeat", "scripts/lease_heartbeat.py")
    ledger = tmp_path / "l.jsonl"
    _seed(ledger, "lease-fresh", datetime.now(timezone.utc) - timedelta(minutes=2))
    assert mod.find_missed(ledger, grace_minutes=15) == []


def test_mark_missed_stale_mutates(tmp_path):
    mod = _load("lease_heartbeat", "scripts/lease_heartbeat.py")
    ledger = tmp_path / "l.jsonl"
    _seed(ledger, "lease-stale", datetime.now(timezone.utc) - timedelta(minutes=60))
    res = mod.mark_missed_stale(ledger, grace_minutes=15)
    assert res["marked_stale"] == ["lease-stale"]
    lm = _lm()
    assert lm.load_ledger(ledger)[0]["status"] == "stale"


def test_summarize_reports_missed(tmp_path):
    mod = _load("lease_heartbeat", "scripts/lease_heartbeat.py")
    ledger = tmp_path / "l.jsonl"
    _seed(ledger, "lease-stale", datetime.now(timezone.utc) - timedelta(minutes=60))
    out = mod.summarize(ledger)
    assert out["status"] == "missed_heartbeats_detected"
    assert out["missed_count"] == 1


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
