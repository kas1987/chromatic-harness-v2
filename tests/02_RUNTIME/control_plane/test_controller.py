"""Tests for control_plane.controller (proportional quota controller)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# Import budget.quota_state first so the module is available for controller.
from budget.quota_state import (  # noqa: E402
    MANUAL_SEED_TTL_SECONDS,
    STALENESS_SECONDS,
    QuotaState,
    QuotaStateReader,
)
from control_plane.controller import (  # noqa: E402
    C_MAX,
    C_MIN,
    DEADBAND_PCT,
    HYSTERESIS_TICKS,
    MAX_STEP_PER_TICK,
    NEUTRAL_THRESHOLD,
    TARGET_PCT,
    OverlayDecision,
    _axis_d_exhausted,
    _clamp,
    _hours_until,
    _parse_ts,
    _read_forecast,
    _read_overlay_state,
    compute_decision,
    run_once,
)

_NOW = datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc)


def _fresh_state(weekly_pct: float = 85.0, **kwargs) -> QuotaState:
    """Return a fresh QuotaState captured 10 seconds ago."""
    captured = (_NOW - timedelta(seconds=10)).isoformat()
    return QuotaState(
        weekly_pct=weekly_pct,
        captured_at=captured,
        present=True,
        source="proxy",
        **kwargs,
    )


def _stale_state() -> QuotaState:
    """Return a QuotaState that is older than STALENESS_SECONDS."""
    captured = (_NOW - timedelta(seconds=STALENESS_SECONDS + 60)).isoformat()
    return QuotaState(weekly_pct=50.0, captured_at=captured, present=True, source="proxy")


# ── _clamp ────────────────────────────────────────────────────────────────────


def test_clamp_within_bounds() -> None:
    assert _clamp(3, 1, 4) == 3


def test_clamp_below_lo() -> None:
    assert _clamp(0, 1, 4) == 1


def test_clamp_above_hi() -> None:
    assert _clamp(9, 1, 4) == 4


def test_clamp_at_bounds() -> None:
    assert _clamp(1, 1, 4) == 1
    assert _clamp(4, 1, 4) == 4


# ── _parse_ts ─────────────────────────────────────────────────────────────────


def test_parse_ts_iso_format() -> None:
    dt = _parse_ts("2026-06-03T12:00:00+00:00")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_ts_z_suffix() -> None:
    dt = _parse_ts("2026-06-03T12:00:00Z")
    assert dt is not None


def test_parse_ts_none() -> None:
    assert _parse_ts(None) is None


def test_parse_ts_invalid() -> None:
    assert _parse_ts("not-a-date") is None


# ── _hours_until ──────────────────────────────────────────────────────────────


def test_hours_until_future() -> None:
    future = (_NOW + timedelta(hours=5)).isoformat()
    result = _hours_until(future, now=_NOW)
    assert result is not None
    assert abs(result - 5.0) < 0.01


def test_hours_until_past() -> None:
    past = (_NOW - timedelta(hours=1)).isoformat()
    result = _hours_until(past, now=_NOW)
    assert result is not None
    assert result < 0


def test_hours_until_invalid() -> None:
    assert _hours_until("bad", now=_NOW) is None


# ── _axis_d_exhausted ─────────────────────────────────────────────────────────


def test_axis_d_not_exhausted_when_remaining() -> None:
    forecast = {"limits": {"daily": {"remaining_usd": 10.0}}}
    assert not _axis_d_exhausted(forecast)


def test_axis_d_exhausted_daily_zero() -> None:
    forecast = {"limits": {"daily": {"remaining_usd": 0.0}}}
    assert _axis_d_exhausted(forecast)


def test_axis_d_exhausted_monthly_zero() -> None:
    forecast = {"limits": {"monthly": {"remaining_usd": 0.0}}}
    assert _axis_d_exhausted(forecast)


def test_axis_d_exhausted_via_forecast_flag() -> None:
    forecast = {"forecast": {"daily_over_cap": True}}
    assert _axis_d_exhausted(forecast)


def test_axis_d_exhausted_monthly_over_cap() -> None:
    forecast = {"forecast": {"monthly_over_cap": True}}
    assert _axis_d_exhausted(forecast)


def test_axis_d_not_exhausted_empty() -> None:
    assert not _axis_d_exhausted({})


# ── _read_overlay_state ───────────────────────────────────────────────────────


def test_read_overlay_state_missing_file(tmp_path: Path) -> None:
    prev, pdir, pticks = _read_overlay_state(tmp_path / "nonexistent.json")
    assert prev == NEUTRAL_THRESHOLD
    assert pdir == 0
    assert pticks == 0


def test_read_overlay_state_reads_hysteresis(tmp_path: Path) -> None:
    overlay_file = tmp_path / "overlay.json"
    overlay_file.write_text(
        json.dumps(
            {
                "c_to_t_threshold": 2,
                "_hysteresis": {"previous_threshold": 2, "pending_dir": -1, "pending_ticks": 1},
            }
        ),
        encoding="utf-8",
    )
    prev, pdir, pticks = _read_overlay_state(overlay_file)
    assert prev == 2
    assert pdir == -1
    assert pticks == 1


def test_read_overlay_state_clamped(tmp_path: Path) -> None:
    overlay_file = tmp_path / "overlay.json"
    overlay_file.write_text(json.dumps({"_hysteresis": {"previous_threshold": 99}}), encoding="utf-8")
    prev, _, _ = _read_overlay_state(overlay_file)
    assert prev <= C_MAX


# ── _read_forecast ────────────────────────────────────────────────────────────


def test_read_forecast_missing(tmp_path: Path) -> None:
    result = _read_forecast(tmp_path / "nope.json")
    assert result == {}


def test_read_forecast_valid(tmp_path: Path) -> None:
    fc = {"axis_prepaid": {"projected_close_pct": 80.0}}
    p = tmp_path / "forecast.json"
    p.write_text(json.dumps(fc), encoding="utf-8")
    result = _read_forecast(p)
    assert result["axis_prepaid"]["projected_close_pct"] == 80.0


# ── compute_decision ──────────────────────────────────────────────────────────


def test_compute_decision_staleness_fallback() -> None:
    state = _stale_state()
    decision = compute_decision(
        state,
        {},
        previous_threshold=NEUTRAL_THRESHOLD,
        pending_dir=0,
        pending_ticks=0,
        now=_NOW,
    )
    assert decision.staleness_fallback is True
    assert decision.allow_paid_spill is False


def test_compute_decision_deadband_hold() -> None:
    # At exactly target, should hold
    state = _fresh_state(weekly_pct=TARGET_PCT)
    decision = compute_decision(
        state,
        {},
        previous_threshold=NEUTRAL_THRESHOLD,
        pending_dir=0,
        pending_ticks=0,
        now=_NOW,
    )
    assert decision.direction == 0
    assert decision.deadband_hold is True


def test_compute_decision_under_target_lowers_bar() -> None:
    # Well below target (low usage of prepaid quota)
    state = _fresh_state(weekly_pct=50.0)
    decision = compute_decision(
        state,
        {},
        previous_threshold=NEUTRAL_THRESHOLD,
        pending_dir=0,
        pending_ticks=0,
        now=_NOW,
    )
    assert decision.direction == -1


def test_compute_decision_over_target_raises_bar() -> None:
    # Well above target
    state = _fresh_state(weekly_pct=98.0)
    decision = compute_decision(
        state,
        {},
        previous_threshold=NEUTRAL_THRESHOLD,
        pending_dir=0,
        pending_ticks=0,
        now=_NOW,
    )
    assert decision.direction == +1


def test_compute_decision_hysteresis_pending() -> None:
    # First tick in a direction: should not move yet
    state = _fresh_state(weekly_pct=50.0)
    decision = compute_decision(
        state,
        {},
        previous_threshold=NEUTRAL_THRESHOLD,
        pending_dir=-1,
        pending_ticks=0,
        now=_NOW,
    )
    # After 1 tick (< HYSTERESIS_TICKS), threshold should not move
    assert decision.c_to_t_threshold == NEUTRAL_THRESHOLD
    assert decision.pending_ticks == 1


def test_compute_decision_hysteresis_satisfied_moves() -> None:
    # Enough consecutive ticks to trigger a move
    state = _fresh_state(weekly_pct=50.0)
    decision = compute_decision(
        state,
        {},
        previous_threshold=NEUTRAL_THRESHOLD,
        pending_dir=-1,
        pending_ticks=HYSTERESIS_TICKS - 1,
        now=_NOW,
    )
    assert decision.c_to_t_threshold < NEUTRAL_THRESHOLD


def test_compute_decision_lockout_risk_raises_bar() -> None:
    state = _fresh_state(weekly_pct=50.0, status="rejected")
    decision = compute_decision(
        state,
        {},
        previous_threshold=NEUTRAL_THRESHOLD,
        pending_dir=0,
        pending_ticks=0,
        now=_NOW,
    )
    assert decision.direction == +1


def test_compute_decision_axis_d_exhausted_forbids_spill() -> None:
    state = _fresh_state(weekly_pct=85.0)
    forecast = {"limits": {"daily": {"remaining_usd": 0.0}}}
    decision = compute_decision(
        state,
        forecast,
        previous_threshold=NEUTRAL_THRESHOLD,
        pending_dir=0,
        pending_ticks=0,
        now=_NOW,
    )
    assert decision.allow_paid_spill is False


def test_compute_decision_threshold_clamped_at_c_max() -> None:
    # Already at maximum, staleness pushes up but should be clamped
    state = _stale_state()
    decision = compute_decision(
        state,
        {},
        previous_threshold=C_MAX,
        pending_dir=0,
        pending_ticks=0,
        now=_NOW,
    )
    assert decision.c_to_t_threshold <= C_MAX


def test_compute_decision_threshold_clamped_at_c_min() -> None:
    state = _fresh_state(weekly_pct=1.0)
    # Enough ticks to trigger a move downward from C_MIN
    decision = compute_decision(
        state,
        {},
        previous_threshold=C_MIN,
        pending_dir=-1,
        pending_ticks=HYSTERESIS_TICKS,
        now=_NOW,
    )
    assert decision.c_to_t_threshold >= C_MIN


def test_compute_decision_overlay_dict_structure() -> None:
    state = _fresh_state(weekly_pct=85.0)
    decision = compute_decision(
        state,
        {},
        previous_threshold=NEUTRAL_THRESHOLD,
        pending_dir=0,
        pending_ticks=0,
        now=_NOW,
    )
    overlay = decision.to_overlay(now=_NOW)
    assert overlay["schema"] == "routing_policy_overlay/v1"
    assert "c_to_t_threshold" in overlay
    assert "allow_paid_spill" in overlay
    assert "_hysteresis" in overlay


def test_compute_decision_reasons_non_empty() -> None:
    state = _fresh_state(weekly_pct=50.0)
    decision = compute_decision(
        state,
        {},
        previous_threshold=NEUTRAL_THRESHOLD,
        pending_dir=0,
        pending_ticks=0,
        now=_NOW,
    )
    assert len(decision.reasons) > 0


def test_overlay_decision_changed_property() -> None:
    d = OverlayDecision(
        c_to_t_threshold=2,
        previous_threshold=3,
        direction=-1,
        allow_paid_spill=True,
        staleness_fallback=False,
        deadband_hold=False,
    )
    assert d.changed is True


def test_overlay_decision_not_changed() -> None:
    d = OverlayDecision(
        c_to_t_threshold=3,
        previous_threshold=3,
        direction=0,
        allow_paid_spill=True,
        staleness_fallback=False,
        deadband_hold=True,
    )
    assert d.changed is False


# ── run_once ──────────────────────────────────────────────────────────────────


def test_run_once_writes_overlay(tmp_path: Path) -> None:
    overlay_path = tmp_path / "overlay.json"
    forecast_path = tmp_path / "forecast.json"
    quota_state_path = tmp_path / "quota_state.json"

    # Write a stale quota state (no fresh data) — controller should use staleness fallback
    decision = run_once(
        quota_state_path=quota_state_path,
        forecast_path=forecast_path,
        overlay_path=overlay_path,
        now=_NOW,
    )
    assert overlay_path.is_file()
    data = json.loads(overlay_path.read_text(encoding="utf-8"))
    assert data["schema"] == "routing_policy_overlay/v1"
    assert isinstance(decision, OverlayDecision)


def test_run_once_with_fresh_quota_state(tmp_path: Path) -> None:
    overlay_path = tmp_path / "overlay.json"
    quota_path = tmp_path / "quota_state.json"
    captured = (_NOW - timedelta(seconds=30)).isoformat()
    quota_path.write_text(
        json.dumps({"weekly_pct": 85.0, "captured_at": captured, "source": "proxy"}),
        encoding="utf-8",
    )
    decision = run_once(
        quota_state_path=quota_path,
        overlay_path=overlay_path,
        now=_NOW,
    )
    assert not decision.staleness_fallback
    assert decision.c_to_t_threshold in range(C_MIN, C_MAX + 1)


def test_run_once_manual_seed_uses_extended_ttl(tmp_path: Path) -> None:
    overlay_path = tmp_path / "overlay.json"
    quota_path = tmp_path / "quota_state.json"
    # Manually seeded state 1 hour ago — within 24h TTL but outside 5-min standard TTL
    captured = (_NOW - timedelta(hours=1)).isoformat()
    quota_path.write_text(
        json.dumps({"weekly_pct": 70.0, "captured_at": captured, "source": "manual"}),
        encoding="utf-8",
    )
    decision = run_once(
        quota_state_path=quota_path,
        overlay_path=overlay_path,
        now=_NOW,
    )
    # Manual seed at 1h old should be within 24h TTL and NOT trigger staleness fallback
    assert not decision.staleness_fallback


def test_run_once_projected_close_overrides_weekly_pct(tmp_path: Path) -> None:
    overlay_path = tmp_path / "overlay.json"
    quota_path = tmp_path / "quota_state.json"
    forecast_path = tmp_path / "forecast.json"

    captured = (_NOW - timedelta(seconds=30)).isoformat()
    quota_path.write_text(
        json.dumps({"weekly_pct": 95.0, "captured_at": captured, "source": "proxy"}),
        encoding="utf-8",
    )
    forecast_path.write_text(
        json.dumps({"axis_prepaid": {"projected_close_pct": 50.0}}),
        encoding="utf-8",
    )
    decision = run_once(
        quota_state_path=quota_path,
        forecast_path=forecast_path,
        overlay_path=overlay_path,
        now=_NOW,
    )
    # Projected 50% < target 90% → should lower bar (direction=-1), but hysteresis may hold
    assert decision.direction in (-1, 0)
