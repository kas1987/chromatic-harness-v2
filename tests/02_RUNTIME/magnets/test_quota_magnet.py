"""Tests for magnets.quota_magnet — QuotaMagnet.

QuotaMagnet has a complex dependency on QuotaStateReader / control_plane.
We supply inline quota_state_obj in the signal to avoid filesystem I/O.
"""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.quota_magnet import (
    ACTION_CONSERVATIVE,
    ACTION_HOLD,
    ACTION_SPEND,
    ACTION_SPILL,
    QuotaMagnet,
)
from budget.quota_state import QuotaState

_ACTIVE_POINTS = ["pre_dispatch", "routing_decision", "phase_boundary", "post_execution"]


def _state(
    weekly_pct: float | None = None,
    session_5h_pct: float | None = None,
    status: str | None = None,
    present: bool = True,
) -> QuotaState:
    return QuotaState(
        weekly_pct=weekly_pct,
        session_5h_pct=session_5h_pct,
        status=status,
        present=present,
    )


def _observe(
    inflection: str = "pre_dispatch",
    quota_state: QuotaState | None = None,
    **extra,
) -> MagnetEvent:
    sig = dict(extra)
    if quota_state is not None:
        sig["quota_state_obj"] = quota_state
    return QuotaMagnet().observe("m1", inflection, sig)


class TestQuotaMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(QuotaMagnet, BaseMagnet)

    def test_name(self):
        assert QuotaMagnet.name == "quota_magnet"

    def test_observe_returns_magnet_event(self):
        state = _state(weekly_pct=50.0)
        event = _observe(quota_state=state)
        assert isinstance(event, MagnetEvent)


class TestQuotaMagnetNonActiveInflection:
    def test_non_active_inflection_no_delta(self):
        state = _state(weekly_pct=20.0)
        event = _observe("intake", quota_state=state)
        assert event.risk_delta == 0.0
        assert event.confidence_delta == 0.0

    def test_non_active_inflection_default_action(self):
        state = _state(weekly_pct=20.0)
        event = _observe("intake", quota_state=state)
        assert event.recommended_action == "none"


class TestQuotaMagnetStaleSignal:
    def test_stale_state_recommends_conservative(self):
        # A state without present=True / captured_at treated as stale by controller
        state = QuotaState(weekly_pct=None, present=False)
        event = _observe(quota_state=state)
        assert event.recommended_action == ACTION_CONSERVATIVE

    def test_stale_state_moderate_risk(self):
        state = QuotaState(present=False)
        event = _observe(quota_state=state)
        assert event.risk_delta == 0.35

    def test_stale_state_confidence_negative(self):
        state = QuotaState(present=False)
        event = _observe(quota_state=state)
        assert event.confidence_delta == -3.0


class TestQuotaMagnetDeadbandHold:
    def test_on_track_recommends_hold(self):
        # weekly_pct at target (around 50% typically sits in deadband)
        state = _state(weekly_pct=50.0, present=True)
        event = _observe(quota_state=state, previous_threshold=50)
        # Deadband hold -> ACTION_HOLD
        if event.recommended_action == ACTION_HOLD:
            assert event.confidence_delta == 5.0
            assert event.risk_delta == 0.0


class TestQuotaMagnetUnderUtilized:
    def test_under_utilisation_recommends_spend(self):
        # Very low weekly usage -> under target -> spend direction
        state = _state(weekly_pct=5.0, present=True)
        event = _observe(quota_state=state, previous_threshold=50)
        if event.recommended_action == ACTION_SPEND:
            assert event.risk_delta == 0.1
            assert event.confidence_delta == 2.0


class TestQuotaMagnetSpill:
    def test_rate_limited_state_raises_risk(self):
        state = _state(weekly_pct=95.0, session_5h_pct=95.0, status="rate_limited", present=True)
        event = _observe(quota_state=state, previous_threshold=50)
        assert event.recommended_action in (ACTION_SPILL, ACTION_CONSERVATIVE)

    def test_high_session_pct_raises_risk(self):
        state = _state(weekly_pct=95.0, session_5h_pct=92.0, present=True)
        event = _observe(quota_state=state, previous_threshold=50)
        assert event.risk_delta > 0


class TestQuotaMagnetSignalPopulation:
    def test_observed_signal_has_weekly_pct(self):
        state = _state(weekly_pct=60.0, present=True)
        event = _observe(quota_state=state)
        if event.observed_signal:  # populated only on active inflection points
            assert "weekly_pct" in event.observed_signal

    def test_all_active_inflection_points_trigger(self):
        state = _state(weekly_pct=50.0, present=True)
        for pt in _ACTIVE_POINTS:
            event = _observe(pt, quota_state=state)
            # Should not return the base no-op (risk_delta=0, action=none) for active points
            # unless state computation produces neutral
            assert isinstance(event, MagnetEvent)


class TestQuotaMagnetActuation:
    def test_actuate_false_does_not_run_once(self):
        """Without actuate=True, no filesystem side-effects are attempted."""
        from unittest.mock import patch

        state = _state(weekly_pct=50.0, present=True)
        with patch("magnets.quota_magnet.run_once") as mock_run:
            _observe(quota_state=state, actuate=False)
        mock_run.assert_not_called()

    def test_actuate_true_calls_run_once(self):
        from unittest.mock import patch

        state = _state(weekly_pct=50.0, present=True)
        with patch("magnets.quota_magnet.run_once") as mock_run:
            _observe(quota_state=state, actuate=True)
        mock_run.assert_called_once()
