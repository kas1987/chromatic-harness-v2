"""Tests for magnets.dispatch_magnet — DispatchMagnet."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.dispatch_magnet import DispatchMagnet

_DISPATCH_POINTS = ["dispatch", "pre_execution", "assign"]


class TestDispatchMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(DispatchMagnet, BaseMagnet)

    def test_name(self):
        assert DispatchMagnet.name == "dispatch_magnet"

    def test_observe_returns_magnet_event(self):
        event = DispatchMagnet().observe("m1", "dispatch", {})
        assert isinstance(event, MagnetEvent)


class TestDispatchMagnetNonDispatchInflection:
    def test_non_dispatch_no_delta(self):
        event = DispatchMagnet().observe("m1", "intake", {})
        assert event.risk_delta == 0.0

    def test_non_dispatch_no_evidence(self):
        event = DispatchMagnet().observe("m1", "plan", {})
        assert event.evidence == []

    def test_non_dispatch_default_action(self):
        event = DispatchMagnet().observe("m1", "validation", {})
        assert event.recommended_action == "none"


class TestDispatchMagnetAllControlsMissing:
    def test_no_controls_raises_risk(self):
        event = DispatchMagnet().observe("m1", "dispatch", {})
        assert event.risk_delta > 0

    def test_no_controls_recommends_halt_or_lock(self):
        event = DispatchMagnet().observe("m1", "dispatch", {})
        assert event.recommended_action in ("halt_and_review", "lock_controls")

    def test_no_agent_evidence(self):
        event = DispatchMagnet().observe("m1", "dispatch", {})
        assert any("No agent assigned" in e for e in event.evidence)

    def test_no_tools_evidence(self):
        event = DispatchMagnet().observe("m1", "dispatch", {})
        assert any("Tool allowlist not locked" in e for e in event.evidence)

    def test_no_scope_evidence(self):
        event = DispatchMagnet().observe("m1", "dispatch", {})
        assert any("File scope not set" in e for e in event.evidence)

    def test_no_budget_evidence(self):
        event = DispatchMagnet().observe("m1", "dispatch", {})
        assert any("Budget not set" in e for e in event.evidence)

    def test_no_snapshot_evidence(self):
        event = DispatchMagnet().observe("m1", "dispatch", {})
        assert any("No pre-execution state snapshot" in e for e in event.evidence)


class TestDispatchMagnetAllControlsPresent:
    def _full_signal(self):
        return {
            "agent": "worker-1",
            "allowed_tools": ["git", "edit"],
            "budget": 1000,
            "file_scope": ["src/x.py"],
            "state_snapshot": {"sha": "abc123"},
        }

    def test_all_controls_no_risk(self):
        event = DispatchMagnet().observe("m1", "dispatch", self._full_signal())
        assert event.risk_delta == 0.0

    def test_all_controls_positive_confidence(self):
        event = DispatchMagnet().observe("m1", "dispatch", self._full_signal())
        assert event.confidence_delta > 0

    def test_all_controls_recommend_proceed(self):
        event = DispatchMagnet().observe("m1", "dispatch", self._full_signal())
        assert event.recommended_action == "proceed"

    def test_all_controls_no_evidence(self):
        event = DispatchMagnet().observe("m1", "dispatch", self._full_signal())
        assert event.evidence == []

    def test_all_dispatch_inflection_points(self):
        for pt in _DISPATCH_POINTS:
            event = DispatchMagnet().observe("m1", pt, self._full_signal())
            assert event.recommended_action == "proceed", f"failed for {pt}"


class TestDispatchMagnetPartialControls:
    def test_missing_agent_only_medium_risk(self):
        event = DispatchMagnet().observe(
            "m1", "dispatch",
            {
                "allowed_tools": ["git"],
                "budget": 500,
                "file_scope": ["src/"],
                "state_snapshot": {"sha": "abc"},
            },
        )
        assert 0 < event.risk_delta < 0.5

    def test_agent_alias_assigned_agent(self):
        """assigned_agent key should be recognized as well as agent."""
        event = DispatchMagnet().observe(
            "m1", "dispatch",
            {
                "assigned_agent": "worker-2",
                "allowed_tools": ["git"],
                "budget": 500,
                "file_scope": ["src/"],
                "state_snapshot": {"sha": "abc"},
            },
        )
        assert not any("No agent assigned" in e for e in event.evidence)

    def test_zero_budget_raises_risk(self):
        event = DispatchMagnet().observe(
            "m1", "dispatch", {"agent": "w1", "budget": 0}
        )
        assert any("Budget not set" in e for e in event.evidence)

    def test_negative_budget_raises_risk(self):
        event = DispatchMagnet().observe(
            "m1", "dispatch", {"agent": "w1", "budget": -100}
        )
        assert any("Budget not set" in e for e in event.evidence)

    def test_positive_budget_no_budget_evidence(self):
        event = DispatchMagnet().observe(
            "m1", "dispatch", {"agent": "w1", "budget": 1}
        )
        assert not any("Budget not set" in e for e in event.evidence)


class TestDispatchMagnetRiskCap:
    def test_risk_never_exceeds_1(self):
        # No controls + huge imaginary risk
        event = DispatchMagnet().observe("m1", "dispatch", {})
        assert event.risk_delta <= 1.0
