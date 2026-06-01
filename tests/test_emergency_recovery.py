"""Tests for emergency_recovery.py (k9j7 / gh-108). Network-free, tmp-isolated."""

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


def _seed_lease(ledger: Path, *, active: bool, lease_id: str = "lease-x", owner: str = "AgentA") -> None:
    lm = _lm()
    delta = timedelta(hours=1) if active else timedelta(hours=-1)
    exp = (datetime.now(timezone.utc) + delta).isoformat().replace("+00:00", "Z")
    rec = {
        "lease_id": lease_id,
        "task_id": "T",
        "owner_agent": owner,
        "resources": ["scripts/foo.py"],
        "mode": "exclusive",
        "risk_tier": "T2",
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
        "expires_at": exp,
        "heartbeat_at": "2026-01-01T00:00:00Z",
        "rollback_plan": "none",
        "metadata": {},
    }
    records = lm.load_ledger(ledger)
    records.append(rec)
    lm.write_ledger(ledger, records)


def _mod():
    return _load("emergency_recovery", "scripts/emergency_recovery.py")


def test_inspect_clean_when_no_leases(tmp_path):
    er = _mod()
    out = er.inspect(tmp_path / "l.jsonl")
    assert out["mode"] == "inspect"
    assert out["stale_count"] == 0
    assert "no recovery action required" in out["recommendations"][0]


def test_inspect_flags_stale(tmp_path):
    er = _mod()
    ledger = tmp_path / "l.jsonl"
    _seed_lease(ledger, active=False, lease_id="lease-stale")
    out = er.inspect(ledger)
    assert out["stale_count"] == 1
    assert any("stale" in r for r in out["recommendations"])


def test_stop_condition_active_owner(tmp_path):
    er = _mod()
    ledger = tmp_path / "l.jsonl"
    _seed_lease(ledger, active=True, lease_id="lease-live")
    lm = _lm()
    target = lm.load_ledger(ledger)[0]
    stops = er.assess_stop_conditions(target_lease=target, rollback_plan="rb", ledger=ledger)
    assert "active_owner" in stops


def test_stop_condition_missing_rollback(tmp_path):
    er = _mod()
    stops = er.assess_stop_conditions(target_lease=None, rollback_plan="", ledger=tmp_path / "l.jsonl")
    assert "missing_rollback" in stops


def test_recover_blocked_when_owner_active(tmp_path):
    er = _mod()
    ledger = tmp_path / "l.jsonl"
    _seed_lease(ledger, active=True, lease_id="lease-live")
    res = er.recover_stale_lease(
        "lease-live",
        "AgentA",
        "stale owner",
        "git checkout -- .",
        apply=True,
        ledger=ledger,
        log_path=tmp_path / "log.jsonl",
    )
    assert res["status"] == "blocked"
    assert "active_owner" in res["stop_conditions"]


def test_recover_blocked_without_rollback(tmp_path):
    er = _mod()
    ledger = tmp_path / "l.jsonl"
    _seed_lease(ledger, active=False, lease_id="lease-stale")
    res = er.recover_stale_lease(
        "lease-stale",
        "AgentA",
        "stale",
        "",
        apply=True,
        ledger=ledger,
        log_path=tmp_path / "log.jsonl",
    )
    assert res["status"] == "blocked"
    assert "missing_rollback" in res["stop_conditions"]


def test_recover_dry_run_when_not_applied(tmp_path):
    er = _mod()
    ledger = tmp_path / "l.jsonl"
    _seed_lease(ledger, active=False, lease_id="lease-stale")
    res = er.recover_stale_lease(
        "lease-stale",
        "AgentA",
        "stale owner",
        "git checkout -- .",
        apply=False,
        ledger=ledger,
        log_path=tmp_path / "log.jsonl",
    )
    assert res["status"] == "dry_run"
    # ledger untouched (still active status on record)
    lm = _lm()
    assert lm.load_ledger(ledger)[0]["status"] == "active"


def test_recover_expires_when_applied(tmp_path):
    er = _mod()
    ledger = tmp_path / "l.jsonl"
    _seed_lease(ledger, active=False, lease_id="lease-stale")
    res = er.recover_stale_lease(
        "lease-stale",
        "AgentA",
        "stale owner / human approved",
        "git checkout -- .",
        apply=True,
        ledger=ledger,
        log_path=tmp_path / "log.jsonl",
    )
    assert res["status"] == "expired"
    lm = _lm()
    assert lm.load_ledger(ledger)[0]["status"] == "expired"


def test_recover_not_found(tmp_path):
    er = _mod()
    res = er.recover_stale_lease(
        "nope",
        "AgentA",
        "x",
        "rb",
        apply=True,
        ledger=tmp_path / "l.jsonl",
        log_path=tmp_path / "log.jsonl",
    )
    assert res["status"] == "not_found"


def test_every_action_is_logged(tmp_path):
    er = _mod()
    ledger = tmp_path / "l.jsonl"
    log = tmp_path / "log.jsonl"
    _seed_lease(ledger, active=False, lease_id="lease-stale")
    er.recover_stale_lease("lease-stale", "AgentA", "stale", "rb", apply=True, ledger=ledger, log_path=log)
    rows = er.read_log(log)
    assert rows and rows[-1]["action"] == "stale_lease_recovery" and rows[-1]["ok"] is True


def test_summarize_fail_open_and_artifact(tmp_path):
    er = _mod()
    ledger = tmp_path / "l.jsonl"
    _seed_lease(ledger, active=False, lease_id="lease-stale")
    s = er.summarize(ledger)
    assert s["status"] == "ok"
    assert s["action_required"] is True


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
