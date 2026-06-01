"""Tests for lease_manager.py — lease-based collision control MVP (P0-CC-001 / GH #95).

Network-free; every test uses a tmp ledger so no real state is touched.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("lease_manager", REPO / "scripts" / "lease_manager.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["lease_manager"] = mod
    spec.loader.exec_module(mod)
    return mod


def _acquire(mod, ledger, task, resources, mode="write", tier="T2"):
    rc = mod.acquire(
        Namespace(
            ledger=str(ledger),
            task_id=task,
            owner_agent="tester",
            resources=resources,
            mode=mode,
            risk_tier=tier,
            ttl_minutes=60,
            rollback_plan="git checkout",
        )
    )
    return rc


def test_overlaps_path_semantics():
    mod = _load()
    assert mod.overlaps("scripts/a.py", "scripts/a.py")
    assert mod.overlaps("scripts", "scripts/a.py")  # dir contains file
    assert mod.overlaps("scripts/a.py", "scripts")
    assert not mod.overlaps("scripts/a.py", "scripts/b.py")


def test_acquire_grants_then_conflict_denied(tmp_path):
    mod = _load()
    ledger = tmp_path / "l.jsonl"
    assert _acquire(mod, ledger, "t1", ["scripts/foo.py"]) == 0  # granted
    assert _acquire(mod, ledger, "t2", ["scripts/foo.py"]) == 2  # FR-2 conflict denied


def test_read_leases_do_not_conflict(tmp_path):
    mod = _load()
    ledger = tmp_path / "l.jsonl"
    assert _acquire(mod, ledger, "t1", ["scripts/foo.py"], mode="read") == 0
    assert _acquire(mod, ledger, "t2", ["scripts/foo.py"], mode="read") == 0  # FR-5 read non-blocking


def test_release_frees_resource(tmp_path):
    mod = _load()
    ledger = tmp_path / "l.jsonl"
    _acquire(mod, ledger, "t1", ["scripts/foo.py"])
    records = mod.load_ledger(ledger)
    lease_id = records[0]["lease_id"]
    assert mod.release(Namespace(ledger=str(ledger), lease_id=lease_id)) == 0
    # after release the resource is free again
    assert _acquire(mod, ledger, "t2", ["scripts/foo.py"]) == 0


def test_heartbeat_updates_and_missing_fails(tmp_path):
    mod = _load()
    ledger = tmp_path / "l.jsonl"
    _acquire(mod, ledger, "t1", ["scripts/foo.py"])
    lid = mod.load_ledger(ledger)[0]["lease_id"]
    assert mod.heartbeat(Namespace(ledger=str(ledger), lease_id=lid, extend_minutes=30)) == 0
    assert mod.heartbeat(Namespace(ledger=str(ledger), lease_id="nope", extend_minutes=0)) == 1


def test_expire_marks_lease(tmp_path):
    mod = _load()
    ledger = tmp_path / "l.jsonl"
    _acquire(mod, ledger, "t1", ["scripts/foo.py"])
    lid = mod.load_ledger(ledger)[0]["lease_id"]
    assert mod.expire(Namespace(ledger=str(ledger), lease_id=lid, reason="stale")) == 0
    rec = [r for r in mod.load_ledger(ledger) if r["lease_id"] == lid][0]
    assert rec["status"] == "expired"


def test_summarize_counts_active_and_conflicts(tmp_path):
    mod = _load()
    ledger = tmp_path / "l.jsonl"
    _acquire(mod, ledger, "t1", ["scripts/foo.py"])
    s = mod.summarize(ledger)
    assert s["status"] == "ok" and s["active_leases"] == 1 and s["conflicts"] == 0


def test_lease_schema_validates_acquired_record(tmp_path):
    mod = _load()
    ledger = tmp_path / "l.jsonl"
    _acquire(mod, ledger, "t1", ["scripts/foo.py"])
    rec = mod.load_ledger(ledger)[0]
    schema = json.loads((REPO / "schemas" / "lease.schema.json").read_text(encoding="utf-8"))
    for field in schema["required"]:
        assert field in rec, f"missing required field {field}"


# --- lock_ledger tests ---


def test_lock_ledger_creates_and_removes_lock_file(tmp_path):
    mod = _load()
    ledger = tmp_path / "l.jsonl"
    lock_path = Path(str(ledger) + ".lock")
    with mod.lock_ledger(ledger):
        assert lock_path.exists(), "lock file should exist inside context"
    assert not lock_path.exists(), "lock file should be removed after context exits"


def test_lock_ledger_blocks_concurrent_acquisition(tmp_path):
    """Second lock_ledger call while first is held must raise RuntimeError (fast timeout)."""
    import threading

    mod = _load()
    ledger = tmp_path / "l.jsonl"
    original_timeout = mod._LOCK_TIMEOUT_S
    mod._LOCK_TIMEOUT_S = 0.1  # speed up the test

    errors = []

    def try_lock():
        try:
            with mod.lock_ledger(ledger):
                pass
        except RuntimeError as exc:
            errors.append(exc)

    with mod.lock_ledger(ledger):
        t = threading.Thread(target=try_lock)
        t.start()
        t.join(timeout=5)

    mod._LOCK_TIMEOUT_S = original_timeout
    assert len(errors) == 1, "concurrent lock acquisition should have raised RuntimeError"
    assert "Timed out" in str(errors[0])


def test_heartbeat_does_not_resurrect_expired_lease(tmp_path):
    """Heartbeat on a TTL-expired (but not explicitly marked expired) lease must return not_found."""
    from argparse import Namespace
    from datetime import timedelta

    mod = _load()
    ledger = tmp_path / "l.jsonl"
    # Acquire with a TTL already in the past
    _acquire(mod, ledger, "t1", ["scripts/foo.py"])
    records = mod.load_ledger(ledger)
    lid = records[0]["lease_id"]
    # Back-date the expiry so is_active() returns False
    records[0]["expires_at"] = mod.iso(mod.now() - timedelta(minutes=1))
    mod.write_ledger(ledger, records)

    rc = mod.heartbeat(Namespace(ledger=str(ledger), lease_id=lid, extend_minutes=60))
    assert rc == 1, "heartbeat should return not_found for an expired lease"
    # The expiry timestamp must not have been pushed into the future
    rec = mod.load_ledger(ledger)[0]
    assert mod.now() > mod.datetime.fromisoformat(rec["expires_at"].replace("Z", "+00:00")), (
        "heartbeat must not resurrect an expired lease"
    )


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
