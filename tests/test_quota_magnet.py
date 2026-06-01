"""Tests for QuotaMagnet — the Axis P consumer expressed as a Magnet."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parent.parent / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from budget.quota_state import QuotaState  # noqa: E402
from magnets.quota_magnet import (  # noqa: E402
    ACTION_CONSERVATIVE,
    ACTION_HOLD,
    ACTION_SPEND,
    ACTION_SPILL,
    QuotaMagnet,
)
from magnets.plugin import default_registry  # noqa: E402
from magnets.magnet_orchestrator import MagnetOrchestrator  # noqa: E402


def _fresh_state(**kw) -> QuotaState:
    """A present, fresh QuotaState (captured_at = now)."""
    base = {
        "weekly_pct": kw.get("weekly_pct", 50.0),
        "weekly_reset": kw.get("weekly_reset", "2026-06-05T00:00:00Z"),
        "session_5h_pct": kw.get("session_5h_pct", 10.0),
        "session_5h_reset": kw.get("session_5h_reset", "2026-05-30T23:00:00Z"),
        "status": kw.get("status", "allowed"),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": "test",
    }
    return QuotaState.from_dict(base)


def _observe(state: QuotaState, *, inflection="pre_dispatch", **signal):
    sig = {"quota_state_obj": state, "forecast": signal.pop("forecast", {})}
    sig.update(signal)
    return QuotaMagnet().observe("m1", inflection, sig)


def test_inactive_inflection_is_neutral():
    ev = _observe(_fresh_state(), inflection="mission_start")
    assert ev.risk_delta == 0.0
    assert ev.recommended_action == "none"


def test_under_target_lowers_bar_low_risk():
    # projected far below 90 -> spend prepaid, but only low-grade risk.
    ev = _observe(
        _fresh_state(weekly_pct=20.0),
        forecast={"axis_prepaid": {"projected_close_pct": 20.0}},
    )
    assert ev.recommended_action == ACTION_SPEND
    assert 0.0 < ev.risk_delta < 0.5  # never enough to halt on its own
    assert ev.observed_signal["direction"] == -1


def test_on_track_deadband_holds_positive_confidence():
    ev = _observe(
        _fresh_state(weekly_pct=90.0),
        forecast={"axis_prepaid": {"projected_close_pct": 90.0}},
    )
    assert ev.recommended_action == ACTION_HOLD
    assert ev.risk_delta == 0.0
    assert ev.confidence_delta > 0


def test_lockout_risk_raises_bar_real_risk():
    st = _fresh_state(
        session_5h_pct=95.0,
        session_5h_reset=(datetime.now(timezone.utc)).replace(microsecond=0).isoformat(),
        status="rejected",
    )
    ev = _observe(st)
    assert ev.recommended_action == ACTION_SPILL
    assert ev.risk_delta >= 0.4


def test_stale_signal_conservative_hold():
    stale = QuotaState.from_dict(
        {
            "weekly_pct": 50.0,
            "captured_at": "2000-01-01T00:00:00Z",  # ancient -> not fresh
            "source": "test",
        }
    )
    ev = _observe(stale)
    assert ev.recommended_action == ACTION_CONSERVATIVE
    assert ev.observed_signal["staleness_fallback"] is True


def test_action_vocab_disjoint_from_halt_set():
    # Under-utilisation must NEVER halt a mission.
    halt_words = {"halt_and_revert", "halt", "escalate", "review"}
    for act in (ACTION_SPEND, ACTION_SPILL, ACTION_HOLD, ACTION_CONSERVATIVE):
        assert act not in halt_words


def test_registered_in_default_registry():
    reg = default_registry()
    assert "quota_magnet" in reg.names()
    ev = reg.observe("m1", "quota_magnet", "pre_dispatch", {"quota_state_obj": _fresh_state()})
    assert ev.magnet_name == "quota_magnet"


def test_orchestrator_does_not_halt_on_under_use():
    # A pure under-utilisation event should not push the mission to halt.
    ev = _observe(
        _fresh_state(weekly_pct=10.0),
        forecast={"axis_prepaid": {"projected_close_pct": 10.0}},
    )
    report = MagnetOrchestrator().process("m1", [ev])
    assert report.recommendation != "halt"
