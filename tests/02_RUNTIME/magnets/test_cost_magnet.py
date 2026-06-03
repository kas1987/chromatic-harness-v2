"""Tests for magnets.cost_magnet — CostMagnet (skeleton)."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.cost_magnet import CostMagnet


class TestCostMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(CostMagnet, BaseMagnet)

    def test_name(self):
        assert CostMagnet.name == "cost_magnet"

    def test_observe_returns_magnet_event(self):
        m = CostMagnet()
        event = m.observe("m1", "intake", {})
        assert isinstance(event, MagnetEvent)

    def test_observe_zero_deltas_by_default(self):
        event = CostMagnet().observe("m1", "intake", {})
        assert event.risk_delta == 0.0
        assert event.confidence_delta == 0.0

    def test_observe_passes_signal_through(self):
        sig = {"cost": 100}
        event = CostMagnet().observe("m1", "intake", sig)
        assert event.observed_signal is sig

    def test_observe_sets_magnet_name(self):
        event = CostMagnet().observe("m1", "intake", {})
        assert event.magnet_name == "cost_magnet"

    def test_observe_sets_inflection_point(self):
        event = CostMagnet().observe("m1", "pre_execution", {})
        assert event.inflection_point == "pre_execution"

    def test_observe_sets_mission_id(self):
        event = CostMagnet().observe("mission-7", "intake", {})
        assert event.mission_id == "mission-7"

    def test_observe_empty_evidence(self):
        event = CostMagnet().observe("m1", "intake", {})
        assert event.evidence == []

    def test_observe_default_action(self):
        event = CostMagnet().observe("m1", "intake", {})
        assert event.recommended_action == "none"
