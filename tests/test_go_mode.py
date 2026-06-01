"""Tests for go_mode.py — deterministic GO-mode orchestrator (issue #81).

Network-free: bd is not invoked; queues are injected. Verifies the confidence
formula, band mapping, deterministic selection, dispatch gate, mission-packet
completeness, read-only default, and fail-open summarize().
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("go_mode", REPO / "scripts" / "go_mode.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["go_mode"] = mod  # @dataclass needs the module registered
    spec.loader.exec_module(mod)
    return mod


# ── confidence formula + bands ───────────────────────────────────────────────


def test_confidence_weights_sum_to_one():
    mod = _load()
    assert abs(sum(mod.CONFIDENCE_WEIGHTS.values()) - 1.0) < 1e-9


def test_score_all_high_is_execute_band():
    mod = _load()
    c = mod.score_confidence({k: 100 for k in mod.CONFIDENCE_WEIGHTS})
    assert c["score"] == 100.0
    assert c["band"] == "execute" and c["may_mutate"] is True


def test_score_all_low_halts():
    mod = _load()
    c = mod.score_confidence({k: 0 for k in mod.CONFIDENCE_WEIGHTS})
    assert c["score"] == 0.0
    assert c["band"] == "halt" and c["may_mutate"] is False


def test_missing_factors_default_neutral():
    mod = _load()
    c = mod.score_confidence({})  # all default to 50
    assert c["score"] == 50.0
    assert c["band"] == "plan_only" and c["may_mutate"] is False


def test_confidence_band_boundaries():
    mod = _load()
    assert mod.confidence_band(90)[0] == "execute"
    assert mod.confidence_band(89.9)[0] == "execute_logged"
    assert mod.confidence_band(75)[0] == "execute_logged"
    assert mod.confidence_band(60)[0] == "reversible_only"
    assert mod.confidence_band(59.9)[0] == "plan_only"
    assert mod.confidence_band(40)[0] == "plan_only"
    assert mod.confidence_band(39)[0] == "halt"


# ── deterministic selection ──────────────────────────────────────────────────


def test_select_prefers_p0_then_id():
    mod = _load()
    items = [
        {"id": "b", "priority": "P1", "status": "ready"},
        {"id": "a", "priority": "P0", "status": "ready"},
        {"id": "c", "priority": "P0", "status": "ready"},
    ]
    assert mod.select_next(items)["id"] == "a"  # P0 wins, then id 'a' < 'c'


def test_select_excludes_done_and_blocked():
    mod = _load()
    items = [
        {"id": "x", "priority": "P0", "status": "closed"},
        {"id": "y", "priority": "P0", "status": "ready", "blocked_by": ["z"]},
        {"id": "w", "priority": "P2", "status": "ready"},
    ]
    assert mod.select_next(items)["id"] == "w"  # only unblocked, non-excluded


def test_select_empty_returns_none():
    mod = _load()
    assert mod.select_next([]) is None
    assert mod.select_next([{"id": "x", "status": "deferred"}]) is None


def test_selection_is_deterministic():
    mod = _load()
    items = [{"id": f"t{i}", "priority": "P1", "status": "ready"} for i in range(5)]
    picks = {mod.select_next(list(reversed(items)))["id"] for _ in range(3)}
    assert picks == {"t0"}  # stable id tiebreak regardless of input order


# ── dispatch gate ────────────────────────────────────────────────────────────


def test_dispatch_gate_thresholds():
    mod = _load()
    assert mod.dispatch_allowed({"score": 80}, "high")[0] is True  # >=75 unconditional
    assert mod.dispatch_allowed({"score": 65}, "low")[0] is True  # >=60 + reversible
    assert mod.dispatch_allowed({"score": 65}, "high")[0] is False  # >=60 but high risk
    assert mod.dispatch_allowed({"score": 50}, "low")[0] is False  # below all gates


# ── mission packet completeness (DISPATCH_PLAYBOOK) ──────────────────────────


def test_mission_packet_has_all_required_fields():
    mod = _load()
    item = {
        "id": "chromatic-harness-v2-x",
        "title": "Do a thing",
        "owner_agent": "Auditor",
        "acceptance_checks": ["c1", "c2", "c3"],
        "risk_level": "low",
    }
    conf = mod.score_confidence(mod.estimate_factors(item))
    packet = mod.build_mission_packet(item, conf)
    required = {
        "task_id",
        "objective",
        "repo",
        "allowed_files",
        "forbidden_files",
        "owner_agent",
        "secondary_agent",
        "tool_budget",
        "risk_level",
        "confidence",
        "acceptance_checks",
        "stop_conditions",
        "required_output",
    }
    assert required <= set(packet)
    assert packet["tool_budget"]["max_files"] >= 1  # budget populated
    assert packet["confidence"]["score"] == conf["score"]


# ── full loop + output contract ──────────────────────────────────────────────


def test_run_go_selects_and_scores():
    mod = _load()
    items = [
        {
            "id": "hi",
            "priority": "P0",
            "status": "ready",
            "title": "Rich task",
            "objective": "Clear objective",
            "acceptance_checks": ["validate x", "test y", "check z"],
            "allowed_files": ["a.py"],
            "stop_conditions": ["irreversible"],
            "risk_level": "low",
        },
        {"id": "lo", "priority": "P2", "status": "ready", "title": "Sparse"},
    ]
    rec = mod.run_go(items)
    assert rec["selected"]["id"] == "hi"
    assert rec["confidence"]["score"] >= 75  # rich metadata -> high confidence
    assert rec["dispatch_allowed"] is True
    assert rec["mission_packet"]["task_id"] == "hi"


def test_run_go_empty_queue_is_no_work():
    mod = _load()
    rec = mod.run_go([])
    assert rec["decision"] == "no_work"
    assert rec["dispatch_allowed"] is False
    assert rec["mission_packet"] is None


def test_run_go_never_mutates_repo(tmp_path, monkeypatch):
    # run_go must not write anything unless write_artifact is called explicitly.
    mod = _load()
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "go_mode")
    mod.run_go([{"id": "x", "priority": "P0", "status": "ready", "title": "t"}])
    assert not (tmp_path / "go_mode").exists()  # read-only by default


def test_write_artifact_and_summarize_roundtrip(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "go_mode")
    monkeypatch.setattr(mod, "MISSIONS_DIR", tmp_path / "go_mode" / "missions")
    rec = mod.run_go(
        [
            {
                "id": "x",
                "priority": "P0",
                "status": "ready",
                "title": "t",
                "acceptance_checks": ["test a", "b", "c"],
                "allowed_files": ["f.py"],
                "stop_conditions": ["s"],
                "risk_level": "low",
            }
        ]
    )
    latest, packet = mod.write_artifact(rec)
    assert latest.exists() and packet.exists()
    s = mod.summarize()
    assert s["status"] == "ok"
    assert s["selected_id"] == "x"


def test_summarize_no_scan_fail_open(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path / "empty")
    assert mod.summarize()["status"] == "no_scan"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
