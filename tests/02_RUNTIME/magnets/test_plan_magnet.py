"""Tests for magnets.plan_magnet — PlanMagnet."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.plan_magnet import PlanMagnet

_PLAN_POINTS = ["plan", "post_plan", "decompose", "plan_decompose"]


class TestPlanMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(PlanMagnet, BaseMagnet)

    def test_name(self):
        assert PlanMagnet.name == "plan_magnet"

    def test_observe_returns_magnet_event(self):
        event = PlanMagnet().observe("m1", "plan", {})
        assert isinstance(event, MagnetEvent)


class TestPlanMagnetNonPlanInflection:
    def test_non_plan_inflection_no_delta(self):
        event = PlanMagnet().observe("m1", "intake", {"plan_steps": ["a", "b"]})
        assert event.risk_delta == 0.0
        assert event.confidence_delta == 0.0

    def test_non_plan_inflection_no_evidence(self):
        event = PlanMagnet().observe("m1", "dispatch", {})
        assert event.evidence == []


class TestPlanMagnetPlanSteps:
    def test_no_plan_steps_raises_risk(self):
        event = PlanMagnet().observe("m1", "plan", {"subtasks": [{"id": "0"}]})
        assert event.risk_delta > 0
        assert any("No plan steps" in e for e in event.evidence)

    def test_empty_step_raises_risk(self):
        event = PlanMagnet().observe(
            "m1", "plan", {"plan_steps": ["design", ""], "subtasks": [{"id": "0"}]}
        )
        assert event.risk_delta > 0
        assert any("empty steps" in e for e in event.evidence)

    def test_valid_steps_add_confidence(self):
        event = PlanMagnet().observe(
            "m1", "plan",
            {"plan_steps": ["design", "implement", "test"], "subtasks": [{"id": "0"}]},
        )
        assert event.confidence_delta > 0

    def test_all_plan_inflection_points_active(self):
        for pt in _PLAN_POINTS:
            event = PlanMagnet().observe("m1", pt, {})
            assert event.risk_delta > 0, f"expected risk for {pt} with no steps"


class TestPlanMagnetSubtasks:
    def test_no_subtasks_raises_risk(self):
        event = PlanMagnet().observe("m1", "plan", {"plan_steps": ["a"]})
        assert any("No decomposition" in e for e in event.evidence)

    def test_excessive_subtasks_raises_risk(self):
        subtasks = [{"id": str(i)} for i in range(51)]
        event = PlanMagnet().observe(
            "m1", "plan", {"plan_steps": ["a"], "subtasks": subtasks}
        )
        assert any("Excessive" in e for e in event.evidence)

    def test_valid_subtask_count_adds_confidence(self):
        subtasks = [{"id": str(i)} for i in range(5)]
        event = PlanMagnet().observe(
            "m1", "plan", {"plan_steps": ["a"], "subtasks": subtasks}
        )
        assert event.confidence_delta > 0

    def test_exactly_50_subtasks_is_valid(self):
        subtasks = [{"id": str(i)} for i in range(50)]
        event = PlanMagnet().observe(
            "m1", "plan", {"plan_steps": ["a"], "subtasks": subtasks}
        )
        assert not any("Excessive" in e for e in event.evidence)


class TestPlanMagnetToolFeasibility:
    def test_infeasible_tools_raises_risk(self):
        event = PlanMagnet().observe(
            "m1", "plan",
            {
                "plan_steps": ["a"],
                "subtasks": [{"id": "0"}],
                "tool_requirements": ["git", "k8s"],
                "available_tools": ["git"],
            },
        )
        assert any("Infeasible tools" in e for e in event.evidence)

    def test_feasible_tools_add_confidence(self):
        event = PlanMagnet().observe(
            "m1", "plan",
            {
                "plan_steps": ["a"],
                "subtasks": [{"id": "0"}],
                "tool_requirements": ["git"],
                "available_tools": ["git", "edit"],
            },
        )
        assert not any("Infeasible" in e for e in event.evidence)

    def test_tool_requirements_without_available_raises_risk(self):
        event = PlanMagnet().observe(
            "m1", "plan",
            {
                "plan_steps": ["a"],
                "subtasks": [{"id": "0"}],
                "tool_requirements": ["git"],
                "available_tools": [],
            },
        )
        assert any("no tools available" in e for e in event.evidence)


class TestPlanMagnetGraphValidation:
    def test_cycle_in_graph_detected(self):
        event = PlanMagnet().observe(
            "m1", "plan",
            {
                "plan_steps": ["a", "b"],
                "subtasks": [{"id": "0"}, {"id": "1"}],
                "graph_edges": [["0", "1"], ["1", "0"]],
            },
        )
        assert any("cycle" in e.lower() for e in event.evidence)

    def test_dangling_edge_detected(self):
        event = PlanMagnet().observe(
            "m1", "plan",
            {
                "plan_steps": ["a", "b"],
                "subtasks": [{"id": "0"}, {"id": "1"}],
                "graph_edges": [["0", "99"]],  # 99 doesn't exist
            },
        )
        assert any("Dangling" in e for e in event.evidence)

    def test_valid_acyclic_graph_no_graph_risk(self):
        event = PlanMagnet().observe(
            "m1", "plan",
            {
                "plan_steps": ["a", "b", "c"],
                "subtasks": [{"id": "0"}, {"id": "1"}, {"id": "2"}],
                "graph_edges": [["0", "1"], ["1", "2"]],
            },
        )
        assert not any("Dangling" in e or "cycle" in e.lower() for e in event.evidence)

    def test_malformed_edge_detected(self):
        event = PlanMagnet().observe(
            "m1", "plan",
            {
                "plan_steps": ["a"],
                "subtasks": [{"id": "0"}],
                "graph_edges": ["bad_edge"],
            },
        )
        assert any("Malformed" in e or "edge" in e.lower() for e in event.evidence)


class TestPlanMagnetRecommendedActions:
    def _make_bad_plan(self):
        """Returns a signal that triggers high risk (many issues)."""
        return {
            "plan_steps": [],
            "subtasks": [],
            "tool_requirements": ["git", "k8s", "terraform"],
            "available_tools": [],
        }

    def test_high_risk_recommends_replan(self):
        event = PlanMagnet().observe("m1", "plan", self._make_bad_plan())
        assert event.recommended_action == "replan"

    def test_moderate_risk_recommends_refine(self):
        # Only one issue — no plan steps but good subtasks
        event = PlanMagnet().observe(
            "m1", "plan",
            {"plan_steps": [], "subtasks": [{"id": "0"}]},
        )
        assert event.recommended_action in ("refine_plan", "replan")

    def test_clean_plan_recommends_proceed(self):
        event = PlanMagnet().observe(
            "m1", "plan",
            {
                "plan_steps": ["design", "implement"],
                "subtasks": [{"id": "0"}, {"id": "1"}],
                "graph_edges": [["0", "1"]],
                "tool_requirements": ["git"],
                "available_tools": ["git"],
            },
        )
        assert event.recommended_action == "proceed"
