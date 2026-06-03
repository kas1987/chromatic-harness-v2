"""Tests for magnets.base_magnet — BaseMagnet and MagnetEvent."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent


# ---------------------------------------------------------------------------
# MagnetEvent dataclass
# ---------------------------------------------------------------------------

class TestMagnetEvent:
    def test_required_fields_set(self):
        e = MagnetEvent(
            mission_id="m1",
            magnet_name="test",
            inflection_point="intake",
            observed_signal={"key": "val"},
        )
        assert e.mission_id == "m1"
        assert e.magnet_name == "test"
        assert e.inflection_point == "intake"
        assert e.observed_signal == {"key": "val"}

    def test_defaults(self):
        e = MagnetEvent(
            mission_id="m1",
            magnet_name="test",
            inflection_point="intake",
            observed_signal={},
        )
        assert e.risk_delta == 0.0
        assert e.confidence_delta == 0.0
        assert e.evidence == []
        assert e.recommended_action == "none"

    def test_unique_event_ids(self):
        a = MagnetEvent("m1", "x", "p", {})
        b = MagnetEvent("m1", "x", "p", {})
        assert a.event_id != b.event_id

    def test_timestamp_is_iso_string(self):
        e = MagnetEvent("m1", "x", "p", {})
        assert "T" in e.timestamp  # ISO-8601 format contains 'T'

    def test_explicit_deltas(self):
        e = MagnetEvent(
            mission_id="m1",
            magnet_name="test",
            inflection_point="p",
            observed_signal={},
            risk_delta=0.5,
            confidence_delta=-3.0,
            evidence=["note"],
            recommended_action="review",
        )
        assert e.risk_delta == 0.5
        assert e.confidence_delta == -3.0
        assert e.evidence == ["note"]
        assert e.recommended_action == "review"


# ---------------------------------------------------------------------------
# BaseMagnet
# ---------------------------------------------------------------------------

class TestBaseMagnet:
    def _magnet(self) -> BaseMagnet:
        return BaseMagnet()

    def test_name(self):
        assert BaseMagnet.name == "base_magnet"

    def test_observe_returns_magnet_event(self):
        m = self._magnet()
        event = m.observe("m1", "intake", {"x": 1})
        assert isinstance(event, MagnetEvent)

    def test_observe_copies_signal(self):
        m = self._magnet()
        sig = {"a": 1}
        event = m.observe("m1", "intake", sig)
        assert event.observed_signal is sig

    def test_observe_passes_mission_and_inflection(self):
        m = self._magnet()
        event = m.observe("mission-99", "post_execution", {})
        assert event.mission_id == "mission-99"
        assert event.inflection_point == "post_execution"

    def test_observe_zero_deltas_by_default(self):
        m = self._magnet()
        event = m.observe("m1", "intake", {})
        assert event.risk_delta == 0.0
        assert event.confidence_delta == 0.0

    def test_subclass_can_override_name(self):
        class MyMagnet(BaseMagnet):
            name = "my_magnet"

        assert MyMagnet().name == "my_magnet"

    def test_empty_signal_dict(self):
        m = self._magnet()
        event = m.observe("m1", "intake", {})
        assert event.observed_signal == {}
