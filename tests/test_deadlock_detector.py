"""Tests for deadlock_detector.py (P1-CC-008 / ju0o.7). Network-free, tmp-isolated."""

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


def _seed(ledger: Path, resource: str, agent: str) -> None:
    lm = _lm()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    record = {
        "lease_id": f"lease-{uuid.uuid4().hex[:8]}",
        "task_id": "T",
        "owner_agent": agent,
        "resources": [resource],
        "mode": "exclusive",
        "risk_tier": "T2",
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z",
        "expires_at": future,
        "heartbeat_at": "2026-01-01T00:00:00Z",
        "rollback_plan": "none",
        "metadata": {},
    }
    records = lm.load_ledger(ledger)
    records.append(record)
    lm.write_ledger(ledger, records)


def test_find_cycles_simple():
    mod = _load("deadlock_detector", "scripts/deadlock_detector.py")
    graph = {"A": {"B"}, "B": {"A"}}
    cycles = mod.find_cycles(graph)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B"}


def test_find_cycles_none():
    mod = _load("deadlock_detector", "scripts/deadlock_detector.py")
    graph = {"A": {"B"}, "B": {"C"}}
    assert mod.find_cycles(graph) == []


def test_three_way_cycle():
    mod = _load("deadlock_detector", "scripts/deadlock_detector.py")
    graph = {"A": {"B"}, "B": {"C"}, "C": {"A"}}
    cycles = mod.find_cycles(graph)
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B", "C"}


def test_build_wait_graph_from_leases(tmp_path):
    mod = _load("deadlock_detector", "scripts/deadlock_detector.py")
    ledger = tmp_path / "l.jsonl"
    # A holds r1, B holds r2
    _seed(ledger, "scripts/r1.py", "A")
    _seed(ledger, "scripts/r2.py", "B")
    # A wants r2 (held by B), B wants r1 (held by A) -> cycle
    requests = [
        {"agent": "A", "resource": "scripts/r2.py"},
        {"agent": "B", "resource": "scripts/r1.py"},
    ]
    graph = mod.build_wait_graph(requests, ledger)
    assert graph["A"] == {"B"}
    assert graph["B"] == {"A"}


def test_detect_deadlocks_emits_escalation(tmp_path):
    mod = _load("deadlock_detector", "scripts/deadlock_detector.py")
    ledger = tmp_path / "l.jsonl"
    _seed(ledger, "scripts/r1.py", "A")
    _seed(ledger, "scripts/r2.py", "B")
    requests = [
        {"agent": "A", "resource": "scripts/r2.py"},
        {"agent": "B", "resource": "scripts/r1.py"},
    ]
    result = mod.detect_deadlocks(requests, ledger, write_escalation=False)
    assert result["status"] == "deadlock"
    assert result["cycle_count"] == 1


def test_no_deadlock_when_no_cycle(tmp_path):
    mod = _load("deadlock_detector", "scripts/deadlock_detector.py")
    ledger = tmp_path / "l.jsonl"
    _seed(ledger, "scripts/r1.py", "A")
    requests = [{"agent": "B", "resource": "scripts/r1.py"}]
    result = mod.detect_deadlocks(requests, ledger, write_escalation=False)
    assert result["status"] == "ok"
    assert result["cycle_count"] == 0


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
