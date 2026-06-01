"""Tests for claim_guard.py — queue double-claim protection (P0-CC-003 / ju0o.3).

Network-free; tmp ledger + tmp claim log, no real state touched.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("claim_guard", REPO / "scripts" / "claim_guard.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["claim_guard"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_first_claim_granted(tmp_path):
    cg = _load()
    res = cg.claim("bead-1", "alice", ledger=tmp_path / "l.jsonl", log_path=tmp_path / "log.jsonl")
    assert res["status"] == "granted"


def test_second_agent_cannot_claim_same_item(tmp_path):
    cg = _load()
    ledger, log = tmp_path / "l.jsonl", tmp_path / "log.jsonl"
    cg.claim("bead-1", "alice", ledger=ledger, log_path=log)
    res = cg.claim("bead-1", "bob", ledger=ledger, log_path=log)
    assert res["status"] == "denied"
    assert res["reason"] == "already_claimed"
    assert res["owner_agent"] == "alice"


def test_failed_claim_is_logged(tmp_path):
    cg = _load()
    ledger, log = tmp_path / "l.jsonl", tmp_path / "log.jsonl"
    cg.claim("bead-1", "alice", ledger=ledger, log_path=log)
    cg.claim("bead-1", "bob", ledger=ledger, log_path=log)
    rows = cg.read_log(log)
    denied = [r for r in rows if r["action"] == "claim_denied"]
    assert denied and denied[0]["agent"] == "bob" and denied[0]["ok"] is False


def test_release_frees_for_reclaim(tmp_path):
    cg = _load()
    ledger, log = tmp_path / "l.jsonl", tmp_path / "log.jsonl"
    cg.claim("bead-1", "alice", ledger=ledger, log_path=log)
    cg.release("bead-1", ledger=ledger, log_path=log)
    res = cg.claim("bead-1", "bob", ledger=ledger, log_path=log)
    assert res["status"] == "granted"  # released item is reclaimable


def test_different_beads_do_not_conflict(tmp_path):
    cg = _load()
    ledger, log = tmp_path / "l.jsonl", tmp_path / "log.jsonl"
    assert cg.claim("bead-1", "alice", ledger=ledger, log_path=log)["status"] == "granted"
    assert cg.claim("bead-2", "bob", ledger=ledger, log_path=log)["status"] == "granted"


def test_active_claim_lookup(tmp_path):
    cg = _load()
    ledger, log = tmp_path / "l.jsonl", tmp_path / "log.jsonl"
    cg.claim("bead-1", "alice", ledger=ledger, log_path=log)
    held = cg.active_claim("bead-1", ledger)
    assert held and held["owner_agent"] == "alice"
    assert cg.active_claim("bead-2", ledger) is None


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
