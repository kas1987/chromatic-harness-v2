"""Tests for file_collision_gate.py (P0-CC-004 / ju0o.4).

Network-free and filesystem-isolated via tmp_path.
"""

from __future__ import annotations

import importlib.util
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


def _seed_lease(ledger: Path, resource: str, mode: str = "write", agent: str = "Agent1") -> None:
    """Write a single active lease covering *resource* into *ledger*."""
    lm = _lm()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    import uuid

    record = {
        "lease_id": f"lease-{uuid.uuid4().hex[:8]}",
        "task_id": "T-test",
        "owner_agent": agent,
        "resources": [resource],
        "mode": mode,
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


# ---------------------------------------------------------------------------
# check_write basics
# ---------------------------------------------------------------------------


def test_safe_when_no_leases(tmp_path):
    mod = _load("file_collision_gate", "scripts/file_collision_gate.py")
    ledger = tmp_path / "leases.jsonl"
    result = mod.check_write(["scripts/foo.py"], "AgentA", ledger)
    assert result["status"] == "safe"
    assert result["conflicts"] == []


def test_blocked_when_write_lease_overlaps(tmp_path):
    mod = _load("file_collision_gate", "scripts/file_collision_gate.py")
    ledger = tmp_path / "leases.jsonl"
    _seed_lease(ledger, "scripts/foo.py", mode="write", agent="AgentA")
    result = mod.check_write(["scripts/foo.py"], "AgentB", ledger)
    assert result["status"] == "blocked"
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["blocking_agent"] == "AgentA"


def test_read_lease_does_not_block_write(tmp_path):
    """Read leases must NOT block writes (default behaviour per DoD)."""
    mod = _load("file_collision_gate", "scripts/file_collision_gate.py")
    ledger = tmp_path / "leases.jsonl"
    _seed_lease(ledger, "scripts/foo.py", mode="read", agent="Reader")
    result = mod.check_write(["scripts/foo.py"], "AgentB", ledger)
    assert result["status"] == "safe"


def test_read_lease_blocks_when_opt_in(tmp_path):
    """With allow_read_block=True, read leases also block writes."""
    mod = _load("file_collision_gate", "scripts/file_collision_gate.py")
    ledger = tmp_path / "leases.jsonl"
    _seed_lease(ledger, "scripts/foo.py", mode="read", agent="Reader")
    result = mod.check_write(["scripts/foo.py"], "AgentB", ledger, allow_read_block=True)
    assert result["status"] == "blocked"


def test_path_prefix_overlap_detected(tmp_path):
    """A lease on scripts/ should block writes to scripts/foo.py."""
    mod = _load("file_collision_gate", "scripts/file_collision_gate.py")
    ledger = tmp_path / "leases.jsonl"
    _seed_lease(ledger, "scripts", mode="exclusive", agent="AgentA")
    result = mod.check_write(["scripts/foo.py"], "AgentB", ledger)
    assert result["status"] == "blocked"


def test_non_overlapping_path_safe(tmp_path):
    mod = _load("file_collision_gate", "scripts/file_collision_gate.py")
    ledger = tmp_path / "leases.jsonl"
    _seed_lease(ledger, "scripts/foo.py", mode="write", agent="AgentA")
    result = mod.check_write(["tests/test_bar.py"], "AgentB", ledger)
    assert result["status"] == "safe"


# ---------------------------------------------------------------------------
# list-blocked
# ---------------------------------------------------------------------------


def test_list_blocked_excludes_reads(tmp_path):
    mod = _load("file_collision_gate", "scripts/file_collision_gate.py")
    ledger = tmp_path / "leases.jsonl"
    _seed_lease(ledger, "scripts/foo.py", mode="read", agent="Reader")
    _seed_lease(ledger, "scripts/bar.py", mode="write", agent="Writer")
    blocked = mod.list_blocked_paths(ledger)
    resources = [b["resource"] for b in blocked]
    assert "scripts/bar.py" in resources
    assert "scripts/foo.py" not in resources


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
