"""Tests for magnets.execution_magnet — ExecutionMagnet (skeleton)."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.execution_magnet import ExecutionMagnet


class TestExecutionMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(ExecutionMagnet, BaseMagnet)

    def test_name(self):
        assert ExecutionMagnet.name == "execution_magnet"

    def test_observe_returns_magnet_event(self):
        event = ExecutionMagnet().observe("m1", "post_execution", {})
        assert isinstance(event, MagnetEvent)

    def test_observe_zero_deltas_by_default(self):
        event = ExecutionMagnet().observe("m1", "post_execution", {})
        assert event.risk_delta == 0.0
        assert event.confidence_delta == 0.0

    def test_observe_passes_signal_through(self):
        sig = {"tool_calls": 5, "errors": 0}
        event = ExecutionMagnet().observe("m1", "post_execution", sig)
        assert event.observed_signal is sig

    def test_observe_sets_magnet_name(self):
        event = ExecutionMagnet().observe("m1", "post_execution", {})
        assert event.magnet_name == "execution_magnet"

    def test_observe_sets_mission_id(self):
        event = ExecutionMagnet().observe("mission-99", "post_execution", {})
        assert event.mission_id == "mission-99"

    def test_observe_sets_inflection_point(self):
        event = ExecutionMagnet().observe("m1", "dispatch", {})
        assert event.inflection_point == "dispatch"

    def test_observe_empty_evidence(self):
        event = ExecutionMagnet().observe("m1", "post_execution", {})
        assert event.evidence == []

    def test_observe_default_action_none(self):
        event = ExecutionMagnet().observe("m1", "post_execution", {})
        assert event.recommended_action == "none"
