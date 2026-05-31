"""E2E test for the 7 canonical magnets matching the harness architecture diagram.

Pipeline: INTAKE → PLAN → DISPATCH → EXECUTION → VALIDATION → DECISION → CLOSURE.
Each magnet observes its inflection point; the MagnetOrchestrator then runs the
six-stage feedback pipeline (COLLECT→NORMALIZE→CORRELATE→SCORE→FEEDBACK→RECOMMEND)
over the collected events.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PKG_ROOT = _REPO / "02_RUNTIME"
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

orch_mod = importlib.import_module("magnets.magnet_orchestrator")
plugin_mod = importlib.import_module("magnets.plugin")
decision_mod = importlib.import_module("magnets.decision_magnet")

MagnetOrchestrator = orch_mod.MagnetOrchestrator
default_registry = plugin_mod.default_registry
decide_band = decision_mod.decide_band

CANONICAL = [
    "intake_magnet",
    "plan_magnet",
    "dispatch_magnet",
    "execution_magnet",
    "validation_magnet",
    "decision_magnet",
    "closure_magnet",
]


def test_all_canonical_magnets_registered():
    names = default_registry().names()
    for magnet in CANONICAL:
        assert magnet in names, f"missing canonical magnet: {magnet}"


def test_plan_magnet_flags_infeasible_tools():
    reg = default_registry()
    event = reg.observe(
        "m1",
        "plan_magnet",
        "plan",
        {
            "plan_steps": ["design", "build"],
            "subtasks": [{"id": "0"}, {"id": "1"}],
            "tool_requirements": ["git", "kubernetes"],
            "available_tools": ["git"],
        },
    )
    assert event.risk_delta > 0
    assert any("Infeasible tools" in e for e in event.evidence)


def test_plan_magnet_detects_graph_cycle():
    reg = default_registry()
    event = reg.observe(
        "m1",
        "plan_magnet",
        "plan",
        {
            "plan_steps": ["a", "b"],
            "subtasks": [{"id": "0"}, {"id": "1"}],
            "graph_edges": [["0", "1"], ["1", "0"]],
        },
    )
    assert any("cycle" in e.lower() for e in event.evidence)


def test_dispatch_magnet_flags_missing_controls():
    reg = default_registry()
    event = reg.observe("m1", "dispatch_magnet", "dispatch", {})
    assert event.risk_delta > 0
    assert event.recommended_action in ("halt_and_review", "lock_controls")


def test_dispatch_magnet_passes_when_locked():
    reg = default_registry()
    event = reg.observe(
        "m1",
        "dispatch_magnet",
        "dispatch",
        {
            "agent": "worker-1",
            "allowed_tools": ["git", "edit"],
            "budget": 1000,
            "file_scope": ["scripts/x.py"],
            "state_snapshot": {"sha": "abc"},
        },
    )
    assert event.recommended_action == "proceed"
    assert event.risk_delta == 0.0


def test_validation_magnet_gate_fail_on_test_failure():
    reg = default_registry()
    event = reg.observe(
        "m1",
        "validation_magnet",
        "validation",
        {"tests": {"passed": 10, "failed": 2}},
    )
    assert event.risk_delta > 0
    assert event.observed_signal["validation_passed"] is False


def test_validation_magnet_all_gates_pass():
    reg = default_registry()
    event = reg.observe(
        "m1",
        "validation_magnet",
        "validation",
        {
            "tests": {"passed": 10, "failed": 0},
            "lint": {"ok": True},
            "security": {"ok": True, "findings": []},
        },
    )
    assert event.observed_signal["validation_passed"] is True
    assert event.recommended_action == "proceed"


def test_decision_magnet_bands():
    assert decide_band(95)[0] == "proceed"
    assert decide_band(80)[0] == "proceed_reversible_only"
    assert decide_band(60)[0] == "self_heal"
    assert decide_band(30)[0] == "escalate"


def test_decision_magnet_risk_override():
    reg = default_registry()
    event = reg.observe(
        "m1",
        "decision_magnet",
        "decision",
        {"confidence_score": 95, "risk_score": 0.7},
    )
    # High risk forces escalation despite high confidence
    assert event.recommended_action == "escalate"


def test_full_canonical_pipeline_happy_path():
    """Drive all 7 magnets through their inflection points, then synthesize."""
    reg = default_registry()
    orch = MagnetOrchestrator(reg)
    mission = "m-e2e"

    events = [
        reg.observe(
            mission, "intake_magnet", "intake", {"objective": "Ship feature X cleanly"}
        ),
        reg.observe(
            mission,
            "plan_magnet",
            "plan",
            {
                "plan_steps": ["design", "implement", "test"],
                "subtasks": [{"id": "0"}, {"id": "1"}, {"id": "2"}],
                "graph_edges": [["0", "1"], ["1", "2"]],
                "tool_requirements": ["git"],
                "available_tools": ["git", "edit"],
            },
        ),
        reg.observe(
            mission,
            "dispatch_magnet",
            "dispatch",
            {
                "agent": "worker-1",
                "allowed_tools": ["git", "edit"],
                "budget": 5000,
                "file_scope": ["src/x.py"],
                "state_snapshot": {"sha": "abc123"},
            },
        ),
        reg.observe(
            mission,
            "execution_magnet",
            "post_execution",
            {"tool_calls": 3, "errors": 0},
        ),
        reg.observe(
            mission,
            "validation_magnet",
            "validation",
            {
                "tests": {"passed": 12, "failed": 0},
                "lint": {"ok": True},
                "security": {"ok": True, "findings": []},
            },
        ),
        reg.observe(
            mission,
            "decision_magnet",
            "decision",
            {"confidence_score": 92, "risk_score": 0.05},
        ),
        reg.observe(
            mission,
            "closure_magnet",
            "closure",
            {"validation_passed": True},
        ),
    ]

    report = orch.process(mission, events)
    assert report.collected_count == 7
    magnets_seen = set(report.correlated["magnets_seen"])
    for magnet in CANONICAL:
        assert magnet in magnets_seen, f"{magnet} missing from pipeline report"
    # Happy path: no halts, recommendation should not be halt/review
    assert report.correlated["halt_actions"] == 0
    assert report.recommendation in ("proceed", "proceed_reversible_only")


def test_full_canonical_pipeline_unhappy_path():
    """A failing validation + low confidence should drive the pipeline to replan/halt."""
    reg = default_registry()
    orch = MagnetOrchestrator(reg)
    mission = "m-e2e-bad"

    events = [
        reg.observe(
            mission, "intake_magnet", "intake", {"objective": "x"}
        ),  # too short
        reg.observe(mission, "plan_magnet", "plan", {}),  # no plan
        reg.observe(mission, "dispatch_magnet", "dispatch", {}),  # no controls
        reg.observe(
            mission,
            "validation_magnet",
            "validation",
            {"tests": {"passed": 1, "failed": 5}},
        ),
        reg.observe(
            mission,
            "decision_magnet",
            "decision",
            {"confidence_score": 30, "risk_score": 0.6},
        ),
    ]
    report = orch.process(mission, events)
    assert report.collected_count == 5
    assert report.recommendation in ("halt", "replan", "review")
