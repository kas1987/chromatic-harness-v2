"""Tests for magnets.intake_magnet — IntakeMagnet."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.intake_magnet import IntakeMagnet


class TestIntakeMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(IntakeMagnet, BaseMagnet)

    def test_name(self):
        assert IntakeMagnet.name == "intake_magnet"

    def test_observe_returns_magnet_event(self):
        m = IntakeMagnet()
        event = m.observe("m1", "intake", {"objective": "Do something useful here"})
        assert isinstance(event, MagnetEvent)


class TestIntakeMagnetObjectiveLength:
    def _observe(self, objective: str) -> MagnetEvent:
        return IntakeMagnet().observe("m1", "intake", {"objective": objective})

    # --- short objective (<10 chars) ---
    def test_short_objective_raises_risk(self):
        event = self._observe("short")
        assert event.risk_delta == 0.1

    def test_short_objective_negative_confidence(self):
        event = self._observe("short")
        assert event.confidence_delta == -5.0

    def test_short_objective_clarify_action(self):
        event = self._observe("short")
        assert event.recommended_action == "clarify_intent"

    def test_short_objective_evidence(self):
        event = self._observe("tiny")
        assert "objective_too_short" in event.evidence

    def test_empty_objective_triggers_clarify(self):
        event = self._observe("")
        assert event.recommended_action == "clarify_intent"

    def test_exactly_9_chars_is_short(self):
        event = self._observe("123456789")
        assert event.recommended_action == "clarify_intent"

    # --- valid objective (10-500 chars) ---
    def test_exactly_10_chars_is_valid(self):
        event = self._observe("1234567890")
        assert event.recommended_action == "proceed"

    def test_valid_objective_positive_confidence(self):
        event = self._observe("Ship feature X cleanly and safely")
        assert event.confidence_delta == 2.0

    def test_valid_objective_no_risk(self):
        event = self._observe("A perfectly sized mission objective for testing")
        assert event.risk_delta == 0.0

    def test_exactly_500_chars_is_valid(self):
        event = self._observe("x" * 500)
        assert event.recommended_action == "proceed"

    # --- oversized objective (>500 chars) ---
    def test_oversized_objective_risk(self):
        event = self._observe("y" * 501)
        assert event.risk_delta == 0.05

    def test_oversized_objective_decompose_action(self):
        event = self._observe("z" * 600)
        assert event.recommended_action == "decompose"

    def test_oversized_objective_evidence(self):
        event = self._observe("w" * 501)
        assert "objective_oversized" in event.evidence

    # --- signal passthrough ---
    def test_mission_id_preserved(self):
        event = IntakeMagnet().observe("mission-42", "intake", {"objective": "A valid objective string"})
        assert event.mission_id == "mission-42"

    def test_inflection_point_preserved(self):
        event = IntakeMagnet().observe("m1", "my_inflection", {"objective": "A valid objective string"})
        assert event.inflection_point == "my_inflection"
