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


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
