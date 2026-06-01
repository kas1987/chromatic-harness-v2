"""Tests for stale_lease_recovery.py (P0-CC-005 / ju0o.5).

Network-free and filesystem-isolated via tmp_path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
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


def _make_lease(resource: str, *, expired: bool, mode: str = "write", agent: str = "Agent1") -> dict:
    """Return a lease record dict. expired=True places expiry in the past."""
    if expired:
        expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    else:
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    import uuid

    return {
        "lease_id": f"lease-{uuid.uuid4().hex[:8]}",
        "task_id": "T-test",
        "owner_agent": agent,
        "resources": [resource],
        "mode": mode,
        "risk_tier": "T2",
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
        "expires_at": expires_at,
        "heartbeat_at": "2026-01-01T00:00:00Z",
        "rollback_plan": "none",
        "metadata": {},
    }


def _write_leases(ledger: Path, leases: list[dict]) -> None:
    lm = _lm()
    lm.write_ledger(ledger, leases)


# ---------------------------------------------------------------------------
# scan_stale
# ---------------------------------------------------------------------------


def test_scan_empty_ledger(tmp_path, monkeypatch):
    mod = _load("stale_lease_recovery", "scripts/stale_lease_recovery.py")
    ledger = tmp_path / "leases.jsonl"
    result = mod.scan_stale(ledger)
    assert result["stale_count"] == 0
    assert result["live_count"] == 0


def test_scan_detects_stale_lease(tmp_path, monkeypatch):
    mod = _load("stale_lease_recovery", "scripts/stale_lease_recovery.py")
    ledger = tmp_path / "leases.jsonl"
    _write_leases(ledger, [_make_lease("scripts/foo.py", expired=True)])
    result = mod.scan_stale(ledger)
    assert result["stale_count"] == 1
    assert result["live_count"] == 0
    assert result["stale_leases"][0]["resources"] == ["scripts/foo.py"]


def test_scan_live_lease_not_stale(tmp_path, monkeypatch):
    mod = _load("stale_lease_recovery", "scripts/stale_lease_recovery.py")
    ledger = tmp_path / "leases.jsonl"
    _write_leases(ledger, [_make_lease("scripts/foo.py", expired=False)])
    result = mod.scan_stale(ledger)
    assert result["stale_count"] == 0
    assert result["live_count"] == 1


def test_scan_mixed_stale_and_live(tmp_path, monkeypatch):
    mod = _load("stale_lease_recovery", "scripts/stale_lease_recovery.py")
    ledger = tmp_path / "leases.jsonl"
    _write_leases(
        ledger,
        [
            _make_lease("scripts/foo.py", expired=True),
            _make_lease("scripts/bar.py", expired=False),
        ],
    )
    result = mod.scan_stale(ledger)
    assert result["stale_count"] == 1
    assert result["live_count"] == 1


# ---------------------------------------------------------------------------
# recover_stale
# ---------------------------------------------------------------------------


def test_recover_expires_stale_lease(tmp_path, monkeypatch):
    mod = _load("stale_lease_recovery", "scripts/stale_lease_recovery.py")
    ledger = tmp_path / "leases.jsonl"
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(mod, "ARTIFACT_PATH", tmp_path / "stale_recovery_latest.json")
    _write_leases(ledger, [_make_lease("scripts/foo.py", expired=True)])
    result = mod.recover_stale(ledger, reason="ttl_expired")
    assert result["recovered_count"] == 1
    assert result["recovered"][0]["expire_reason"] == "ttl_expired"


def test_recover_does_not_touch_live_leases(tmp_path, monkeypatch):
    mod = _load("stale_lease_recovery", "scripts/stale_lease_recovery.py")
    ledger = tmp_path / "leases.jsonl"
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(mod, "ARTIFACT_PATH", tmp_path / "stale_recovery_latest.json")
    live = _make_lease("scripts/bar.py", expired=False)
    _write_leases(ledger, [live])
    result = mod.recover_stale(ledger)
    assert result["recovered_count"] == 0
    assert result["live_count"] == 1
    # Verify on-disk the live lease is still active.
    lm = _lm()
    records = lm.load_ledger(ledger)
    assert records[0]["status"] == "active"


def test_recover_writes_artifact(tmp_path, monkeypatch):
    mod = _load("stale_lease_recovery", "scripts/stale_lease_recovery.py")
    ledger = tmp_path / "leases.jsonl"
    artifact = tmp_path / "stale_recovery_latest.json"
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(mod, "ARTIFACT_PATH", artifact)
    _write_leases(ledger, [_make_lease("scripts/foo.py", expired=True)])
    mod.recover_stale(ledger, write_artifact=True)
    assert artifact.exists()
    data = json.loads(artifact.read_text())
    assert data["recovered_count"] == 1


# ---------------------------------------------------------------------------
# summarize (fail-open)
# ---------------------------------------------------------------------------


def test_summarize_ok_when_no_stale(tmp_path, monkeypatch):
    mod = _load("stale_lease_recovery", "scripts/stale_lease_recovery.py")
    ledger = tmp_path / "leases.jsonl"
    result = mod.summarize(ledger)
    assert result["status"] == "ok"
    assert result["stale_count"] == 0


def test_summarize_flags_stale(tmp_path, monkeypatch):
    mod = _load("stale_lease_recovery", "scripts/stale_lease_recovery.py")
    ledger = tmp_path / "leases.jsonl"
    _write_leases(ledger, [_make_lease("scripts/foo.py", expired=True)])
    result = mod.summarize(ledger)
    assert result["status"] == "stale_leases_detected"
    assert result["stale_count"] == 1


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
