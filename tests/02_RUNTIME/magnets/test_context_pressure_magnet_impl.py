"""Tests for magnets.context_pressure_magnet — ContextPressureMagnet."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.context_pressure_magnet import (
    ACTION_CHECKPOINT,
    ACTION_HOLD,
    ACTION_NOW,
    ContextPressureMagnet,
)

_ACTIVE_POINTS = ["pre_dispatch", "phase_boundary", "post_execution", "turn_boundary"]


class TestContextPressureMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(ContextPressureMagnet, BaseMagnet)

    def test_name(self):
        assert ContextPressureMagnet.name == "context_pressure_magnet"

    def test_observe_returns_magnet_event(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 30})
        assert isinstance(event, MagnetEvent)


class TestContextPressureMagnetNonActivePoint:
    def test_non_active_inflection_no_delta(self):
        event = ContextPressureMagnet().observe("m1", "intake", {"context_pct": 90})
        assert event.risk_delta == 0.0
        assert event.confidence_delta == 0.0

    def test_non_active_inflection_default_action(self):
        event = ContextPressureMagnet().observe("m1", "intake", {"context_pct": 90})
        assert event.recommended_action == "none"


class TestContextPressureMagnetNoPctSignal:
    def test_missing_pct_adds_evidence(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {})
        assert any("unknown" in e for e in event.evidence)

    def test_missing_pct_no_action(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {})
        # recommended_action stays "none" when pct is unknown
        assert event.recommended_action == "none"

    def test_invalid_window_adds_evidence(self):
        event = ContextPressureMagnet().observe(
            "m1",
            "pre_dispatch",
            {"used_tokens": 1000, "window_tokens": 0},
        )
        assert any("unknown" in e for e in event.evidence)


class TestContextPressureMagnetHoldBand:
    """Below soft_pct (default 50) -> hold."""

    def test_low_pct_recommends_hold(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 10})
        assert event.recommended_action == ACTION_HOLD

    def test_low_pct_no_risk(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 10})
        assert event.risk_delta == 0.0

    def test_low_pct_no_confidence_delta(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 10})
        assert event.confidence_delta == 0.0

    def test_exactly_at_soft_boundary_is_checkpoint(self):
        # pct == soft_pct (50) -> checkpoint (>= soft is the condition)
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 50})
        assert event.recommended_action == ACTION_CHECKPOINT

    def test_just_below_soft_is_hold(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 49.9})
        assert event.recommended_action == ACTION_HOLD


class TestContextPressureMagnetCheckpointBand:
    """Between soft_pct and hard_pct -> checkpoint compaction."""

    def test_mid_pct_recommends_checkpoint(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 65})
        assert event.recommended_action == ACTION_CHECKPOINT

    def test_checkpoint_moderate_risk(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 65})
        assert event.risk_delta == 0.15

    def test_checkpoint_slight_confidence_reduction(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 65})
        assert event.confidence_delta == -1.0

    def test_just_below_hard_is_checkpoint(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 79.9})
        assert event.recommended_action == ACTION_CHECKPOINT


class TestContextPressureMagnetCompactNowBand:
    """At or above hard_pct (default 80) -> compact now."""

    def test_high_pct_recommends_compact_now(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 85})
        assert event.recommended_action == ACTION_NOW

    def test_at_hard_boundary_compact_now(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 80})
        assert event.recommended_action == ACTION_NOW

    def test_compact_now_high_risk(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 85})
        assert event.risk_delta == 0.4

    def test_compact_now_confidence_reduction(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 85})
        assert event.confidence_delta == -3.0

    def test_100_pct_compact_now(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 100})
        assert event.recommended_action == ACTION_NOW


class TestContextPressureMagnetCustomBands:
    def test_custom_soft_pct(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 30, "soft_pct": 25})
        assert event.recommended_action == ACTION_CHECKPOINT

    def test_custom_hard_pct(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 70, "hard_pct": 60})
        assert event.recommended_action == ACTION_NOW


class TestContextPressureMagnetTokensInput:
    """Test the used_tokens / window_tokens calculation path."""

    def test_computed_pct_below_soft(self):
        # 20k / 100k = 20% -> hold
        event = ContextPressureMagnet().observe(
            "m1",
            "pre_dispatch",
            {"used_tokens": 20000, "window_tokens": 100000},
        )
        assert event.recommended_action == ACTION_HOLD

    def test_computed_pct_above_hard(self):
        # 85k / 100k = 85% -> compact_now
        event = ContextPressureMagnet().observe(
            "m1",
            "pre_dispatch",
            {"used_tokens": 85000, "window_tokens": 100000},
        )
        assert event.recommended_action == ACTION_NOW

    def test_all_active_inflection_points(self):
        for pt in _ACTIVE_POINTS:
            event = ContextPressureMagnet().observe("m1", pt, {"context_pct": 90})
            assert event.recommended_action == ACTION_NOW, f"expected compact_now for {pt}"

    def test_observed_signal_populated(self):
        event = ContextPressureMagnet().observe("m1", "pre_dispatch", {"context_pct": 60})
        assert "context_pct" in event.observed_signal
        assert "soft_pct" in event.observed_signal
        assert "hard_pct" in event.observed_signal
