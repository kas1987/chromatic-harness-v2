"""Tests for magnets.closure_magnet — ClosureMagnet."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.closure_magnet import ClosureMagnet


class TestClosureMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(ClosureMagnet, BaseMagnet)

    def test_name(self):
        assert ClosureMagnet.name == "closure_magnet"

    def test_observe_returns_magnet_event(self):
        event = ClosureMagnet().observe("m1", "closure", {})
        assert isinstance(event, MagnetEvent)


class TestClosureMagnetValidationPassed:
    """When validation_passed=True, ship completion is checked."""

    def test_validation_passed_complete_ship_closes_mission(self):
        """When ship stages are complete, close_mission is recommended."""
        event = ClosureMagnet().observe(
            "m1",
            "closure",
            {
                "validation_passed": True,
                "lean_ok": True,
                "live_ok": True,
                "dod_ok": True,
            },
        )
        assert event.recommended_action == "close_mission"

    def test_validation_passed_complete_ship_confidence_positive(self):
        event = ClosureMagnet().observe(
            "m1",
            "closure",
            {"validation_passed": True, "lean_ok": True, "live_ok": True, "dod_ok": True},
        )
        assert event.confidence_delta == 5.0

    def test_validation_passed_complete_ship_risk_negative(self):
        event = ClosureMagnet().observe(
            "m1",
            "closure",
            {"validation_passed": True, "lean_ok": True, "live_ok": True, "dod_ok": True},
        )
        assert event.risk_delta == -0.05

    def test_validation_passed_incomplete_ship_recommends_replan(self):
        """When ship stages are incomplete, recommend replan."""
        event = ClosureMagnet().observe(
            "m1",
            "closure",
            {
                "validation_passed": True,
                "lean_ok": False,
                "live_ok": False,
                "dod_ok": False,
            },
        )
        assert event.recommended_action == "replan"

    def test_validation_passed_incomplete_ship_negative_confidence(self):
        event = ClosureMagnet().observe(
            "m1",
            "closure",
            {"validation_passed": True, "lean_ok": False, "live_ok": False, "dod_ok": False},
        )
        assert event.confidence_delta == -8.0

    def test_validation_passed_incomplete_ship_positive_risk(self):
        event = ClosureMagnet().observe(
            "m1",
            "closure",
            {"validation_passed": True, "lean_ok": False, "live_ok": False, "dod_ok": False},
        )
        assert event.risk_delta == 0.15

    def test_validation_passed_incomplete_ship_evidence(self):
        event = ClosureMagnet().observe(
            "m1",
            "closure",
            {"validation_passed": True, "lean_ok": False, "live_ok": True, "dod_ok": True},
        )
        assert any("ship_incomplete" in e for e in event.evidence)

    def test_validation_passed_no_ship_flags_closes_mission(self):
        """Without ship flags or log, check_ship_completion returns applicable=False
        so closure proceeds normally."""
        event = ClosureMagnet().observe("m1", "closure", {"validation_passed": True})
        assert event.recommended_action == "close_mission"

    def test_ship_completion_key_in_signal(self):
        event = ClosureMagnet().observe("m1", "closure", {"validation_passed": True})
        assert "ship_completion" in event.observed_signal


class TestClosureMagnetValidationFailed:
    def test_validation_failed_recommends_replan(self):
        event = ClosureMagnet().observe("m1", "closure", {"validation_failed": True})
        assert event.recommended_action == "replan"

    def test_validation_failed_risk_positive(self):
        event = ClosureMagnet().observe("m1", "closure", {"validation_failed": True})
        assert event.risk_delta == 0.2

    def test_validation_failed_confidence_negative(self):
        event = ClosureMagnet().observe("m1", "closure", {"validation_failed": True})
        assert event.confidence_delta == -10.0

    def test_validation_failed_evidence(self):
        event = ClosureMagnet().observe("m1", "closure", {"validation_failed": True})
        assert "validation_failed" in event.evidence


class TestClosureMagnetHandoff:
    """Neither validation_passed nor validation_failed -> handoff."""

    def test_no_validation_signal_recommends_handoff(self):
        event = ClosureMagnet().observe("m1", "closure", {})
        assert event.recommended_action == "handoff"

    def test_handoff_no_risk(self):
        event = ClosureMagnet().observe("m1", "closure", {})
        assert event.risk_delta == 0.0

    def test_handoff_no_confidence_delta(self):
        event = ClosureMagnet().observe("m1", "closure", {})
        assert event.confidence_delta == 0.0


class TestClosureMagnetShipLog:
    """Test the log-scan path of check_ship_completion via ClosureMagnet."""

    def test_ship_log_with_both_stages_closes_mission(self):
        """Both S8 and S10 present plus dod_ok=True -> close_mission."""
        log = "[S8-LEAN] stage passed\n[S10-LIVE] wired=https://example.com proof=deploy-123"
        event = ClosureMagnet().observe("m1", "closure", {"validation_passed": True, "ship_log": log, "dod_ok": True})
        assert event.recommended_action == "close_mission"

    def test_ship_log_missing_dod_recommends_replan(self):
        """S8 + S10 present but dod_ok not set -> ship incomplete -> replan."""
        log = "[S8-LEAN] stage passed\n[S10-LIVE] wired=https://example.com proof=deploy-123"
        event = ClosureMagnet().observe("m1", "closure", {"validation_passed": True, "ship_log": log})
        assert event.recommended_action == "replan"

    def test_ship_log_missing_live_recommends_replan(self):
        log = "[S8-LEAN] stage passed\n# no S10 marker"
        event = ClosureMagnet().observe("m1", "closure", {"validation_passed": True, "ship_log": log, "dod_ok": True})
        assert event.recommended_action == "replan"
