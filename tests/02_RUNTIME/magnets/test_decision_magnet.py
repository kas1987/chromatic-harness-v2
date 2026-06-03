"""Tests for magnets.decision_magnet — DecisionMagnet and decide_band."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.decision_magnet import DecisionMagnet, decide_band


class TestDecideBand:
    """Unit tests for the pure decide_band function."""

    def test_90_to_100_proceeds(self):
        assert decide_band(90)[0] == "proceed"
        assert decide_band(95)[0] == "proceed"
        assert decide_band(100)[0] == "proceed"

    def test_70_to_89_proceed_reversible_only(self):
        assert decide_band(70)[0] == "proceed_reversible_only"
        assert decide_band(80)[0] == "proceed_reversible_only"
        assert decide_band(89)[0] == "proceed_reversible_only"

    def test_50_to_69_self_heal(self):
        assert decide_band(50)[0] == "self_heal"
        assert decide_band(60)[0] == "self_heal"
        assert decide_band(69)[0] == "self_heal"

    def test_below_50_escalate(self):
        assert decide_band(49)[0] == "escalate"
        assert decide_band(30)[0] == "escalate"
        assert decide_band(0)[0] == "escalate"

    def test_returns_tuple_with_next_step(self):
        action, next_step = decide_band(95)
        assert isinstance(action, str)
        assert isinstance(next_step, str)
        assert len(next_step) > 0

    def test_proceed_next_step(self):
        _, next_step = decide_band(95)
        assert next_step == "auto_proceed_to_next_objective"

    def test_proceed_reversible_next_step(self):
        _, next_step = decide_band(80)
        assert next_step == "proceed_with_reversible_actions"

    def test_self_heal_next_step(self):
        _, next_step = decide_band(60)
        assert next_step == "attempt_self_heal_then_recheck"

    def test_escalate_next_step(self):
        _, next_step = decide_band(30)
        assert next_step == "escalate_or_replan"


class TestDecisionMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(DecisionMagnet, BaseMagnet)

    def test_name(self):
        assert DecisionMagnet.name == "decision_magnet"

    def test_observe_returns_magnet_event(self):
        event = DecisionMagnet().observe("m1", "decision", {"confidence_score": 80})
        assert isinstance(event, MagnetEvent)


class TestDecisionMagnetNonDecisionPoint:
    """When inflection_point is not in the decision set, return a plain event."""

    def test_non_decision_inflection_no_delta(self):
        event = DecisionMagnet().observe("m1", "intake", {"confidence_score": 95})
        assert event.risk_delta == 0.0
        assert event.confidence_delta == 0.0

    def test_non_decision_inflection_default_action(self):
        event = DecisionMagnet().observe("m1", "intake", {})
        assert event.recommended_action == "none"


class TestDecisionMagnetBands:
    _DECISION_POINTS = ["decision", "decide", "post_validation", "score_validate"]

    def _observe(self, confidence_score, risk_score=0.0, inflection="decision") -> MagnetEvent:
        return DecisionMagnet().observe(
            "m1", inflection, {"confidence_score": confidence_score, "risk_score": risk_score}
        )

    def test_high_confidence_proceeds(self):
        event = self._observe(95)
        assert event.recommended_action == "proceed"

    def test_high_confidence_positive_confidence_delta(self):
        event = self._observe(95)
        assert event.confidence_delta == 2.0

    def test_mid_high_confidence_reversible(self):
        event = self._observe(80)
        assert event.recommended_action == "proceed_reversible_only"

    def test_mid_confidence_self_heal(self):
        event = self._observe(60)
        assert event.recommended_action == "self_heal"

    def test_low_confidence_escalates(self):
        event = self._observe(30)
        assert event.recommended_action == "escalate"

    def test_low_confidence_negative_delta(self):
        event = self._observe(30)
        assert event.confidence_delta == -5.0
        assert event.risk_delta == 0.1

    def test_all_decision_inflection_points_active(self):
        for pt in self._DECISION_POINTS:
            event = self._observe(95, inflection=pt)
            assert event.recommended_action == "proceed", f"failed for {pt}"

    def test_evidence_contains_confidence_score(self):
        event = self._observe(80)
        assert any("confidence_score" in e for e in event.evidence)

    def test_evidence_contains_risk_score(self):
        event = self._observe(80)
        assert any("risk_score" in e for e in event.evidence)

    def test_evidence_contains_band_action(self):
        event = self._observe(80)
        assert any("band_action" in e for e in event.evidence)

    def test_signal_mutated_with_decision(self):
        event = self._observe(95)
        assert "decision" in event.observed_signal
        assert event.observed_signal["decision"] == "proceed"

    def test_signal_mutated_with_next_step(self):
        event = self._observe(95)
        assert "next_step" in event.observed_signal


class TestDecisionMagnetRiskOverride:
    """High risk_score forces escalation even when confidence is high."""

    def test_high_risk_overrides_high_confidence(self):
        event = DecisionMagnet().observe("m1", "decision", {"confidence_score": 95, "risk_score": 0.5})
        assert event.recommended_action == "escalate"

    def test_high_risk_next_step_is_escalate_high_risk(self):
        event = DecisionMagnet().observe("m1", "decision", {"confidence_score": 95, "risk_score": 0.6})
        assert event.observed_signal["next_step"] == "escalate_high_risk"

    def test_risk_exactly_0_5_overrides(self):
        event = DecisionMagnet().observe("m1", "decision", {"confidence_score": 95, "risk_score": 0.5})
        assert event.recommended_action == "escalate"

    def test_risk_below_0_5_does_not_override(self):
        event = DecisionMagnet().observe("m1", "decision", {"confidence_score": 95, "risk_score": 0.49})
        assert event.recommended_action == "proceed"


class TestDecisionMagnetDefaultValues:
    def test_missing_confidence_score_uses_default(self):
        # Default is 75 which is "proceed_reversible_only"
        event = DecisionMagnet().observe("m1", "decision", {})
        assert event.recommended_action in ("proceed_reversible_only", "proceed")

    def test_invalid_confidence_score_uses_default(self):
        event = DecisionMagnet().observe("m1", "decision", {"confidence_score": "bad"})
        # Should not raise; default 75 -> proceed_reversible_only
        assert event.recommended_action in ("proceed_reversible_only", "proceed")

    def test_none_confidence_score_uses_default(self):
        event = DecisionMagnet().observe("m1", "decision", {"confidence_score": None})
        assert isinstance(event, MagnetEvent)
