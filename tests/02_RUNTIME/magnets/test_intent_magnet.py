"""Tests for magnets.intent_magnet — IntentMagnet (skeleton)."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.intent_magnet import IntentMagnet


class TestIntentMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(IntentMagnet, BaseMagnet)

    def test_name(self):
        assert IntentMagnet.name == "intent_magnet"

    def test_observe_returns_magnet_event(self):
        event = IntentMagnet().observe("m1", "intake", {"intent": "deploy"})
        assert isinstance(event, MagnetEvent)

    def test_observe_zero_deltas_by_default(self):
        event = IntentMagnet().observe("m1", "intake", {})
        assert event.risk_delta == 0.0
        assert event.confidence_delta == 0.0

    def test_observe_passes_signal_through(self):
        sig = {"intent": "ship", "priority": "high"}
        event = IntentMagnet().observe("m1", "intake", sig)
        assert event.observed_signal is sig

    def test_observe_sets_magnet_name(self):
        event = IntentMagnet().observe("m1", "intake", {})
        assert event.magnet_name == "intent_magnet"

    def test_observe_sets_mission_id(self):
        event = IntentMagnet().observe("mission-5", "intake", {})
        assert event.mission_id == "mission-5"

    def test_observe_sets_inflection_point(self):
        event = IntentMagnet().observe("m1", "pre_plan", {})
        assert event.inflection_point == "pre_plan"

    def test_observe_empty_evidence(self):
        event = IntentMagnet().observe("m1", "intake", {})
        assert event.evidence == []

    def test_observe_default_action_none(self):
        event = IntentMagnet().observe("m1", "intake", {})
        assert event.recommended_action == "none"
