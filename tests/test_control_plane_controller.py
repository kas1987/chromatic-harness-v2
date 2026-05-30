"""Tests for the B7 proportional quota controller (TOKEN_ECONOMY_SPEC §7).

Covers the three anti-oscillation / safety properties with mock inputs:
  * deadband around the 90% target -> hold,
  * hysteresis / rate-limiting -> no move until the direction persists,
  * 5-minute staleness guard -> conservative fallback (raise bar, no paid spill),
  * 5h/7d lockout risk -> raise bar,
  * Axis D ($) hard ceiling -> forbid paid spill,
  * gate.py reads the overlay advisory (fail-open).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from budget.quota_state import QuotaState  # noqa: E402
from control_plane import controller as ctrl  # noqa: E402

NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc)


def _state(**kw) -> QuotaState:
    base = dict(
        weekly_pct=80.0,
        weekly_reset=(NOW + timedelta(days=3)).isoformat(),
        session_5h_pct=10.0,
        session_5h_reset=(NOW + timedelta(hours=3)).isoformat(),
        status="allowed",
        captured_at=NOW.isoformat(),
        source="proxy",
        present=True,
    )
    base.update(kw)
    return QuotaState(**base)


def _decide(state, forecast=None, *, prev=3, pdir=0, pticks=0):
    return ctrl.compute_decision(
        state,
        forecast or {},
        previous_threshold=prev,
        pending_dir=pdir,
        pending_ticks=pticks,
        now=NOW,
    )


# --------------------------------------------------------------------------- #
# Deadband                                                                      #
# --------------------------------------------------------------------------- #
def test_deadband_holds_near_target():
    # projected ~89.5 -> within +/-2 of 90 -> hold, no move.
    fc = {"axis_prepaid": {"projected_close_pct": 89.5}}
    d = _decide(_state(weekly_pct=89.5), fc, prev=3)
    assert d.deadband_hold is True
    assert d.c_to_t_threshold == 3
    assert d.direction == 0
    assert d.changed is False


def test_below_deadband_wants_lower_bar():
    fc = {"axis_prepaid": {"projected_close_pct": 70.0}}
    d = _decide(_state(weekly_pct=70.0), fc, prev=3)
    assert d.direction == -1  # under target -> spend prepaid


# --------------------------------------------------------------------------- #
# Hysteresis / rate limiting                                                    #
# --------------------------------------------------------------------------- #
def test_hysteresis_holds_first_tick():
    fc = {"axis_prepaid": {"projected_close_pct": 70.0}}
    # First tick in the "lower" direction: pending, no move yet.
    d = _decide(_state(weekly_pct=70.0), fc, prev=3, pdir=0, pticks=0)
    assert d.c_to_t_threshold == 3  # held
    assert d.pending_dir == -1
    assert d.pending_ticks == 1


def test_hysteresis_moves_after_persisted_direction():
    fc = {"axis_prepaid": {"projected_close_pct": 70.0}}
    # Second consecutive "lower" tick: hysteresis satisfied -> move one step.
    d = _decide(_state(weekly_pct=70.0), fc, prev=3, pdir=-1, pticks=1)
    assert d.c_to_t_threshold == 2  # moved by MAX_STEP_PER_TICK
    assert d.direction == -1
    assert d.pending_ticks == 0  # streak consumed


def test_rate_limit_one_step_per_tick():
    fc = {"axis_prepaid": {"projected_close_pct": 30.0}}
    d = _decide(_state(weekly_pct=30.0), fc, prev=4, pdir=-1, pticks=1)
    # Even with a huge error, the bar moves at most one C-level.
    assert d.c_to_t_threshold == 3


def test_direction_flip_resets_streak():
    fc = {"axis_prepaid": {"projected_close_pct": 70.0}}
    # Was pending +1, now wants -1: streak resets to tick 1, no move.
    d = _decide(_state(weekly_pct=70.0), fc, prev=3, pdir=+1, pticks=1)
    assert d.c_to_t_threshold == 3
    assert d.pending_dir == -1
    assert d.pending_ticks == 1


# --------------------------------------------------------------------------- #
# Staleness guard                                                               #
# --------------------------------------------------------------------------- #
def test_stale_signal_conservative_fallback():
    stale = _state(captured_at=(NOW - timedelta(minutes=10)).isoformat())
    d = _decide(stale, prev=2)
    assert d.staleness_fallback is True
    assert d.allow_paid_spill is False  # do not burn $ on a dead proxy
    assert d.c_to_t_threshold == 3  # raised bar (2 -> 3)
    assert d.direction == +1


def test_missing_signal_is_stale():
    absent = QuotaState(present=False, source="absent")
    d = _decide(absent, prev=3)
    assert d.staleness_fallback is True
    assert d.allow_paid_spill is False


# --------------------------------------------------------------------------- #
# Lockout risk + Axis D ceiling                                                 #
# --------------------------------------------------------------------------- #
def test_5h_lockout_risk_raises_bar():
    state = _state(
        weekly_pct=70.0,
        session_5h_pct=95.0,
        session_5h_reset=(NOW + timedelta(minutes=10)).isoformat(),
    )
    d = _decide(state, prev=2, pdir=+1, pticks=1)
    assert d.direction == +1
    assert d.c_to_t_threshold == 3  # raised to spill C1/C2


def test_rejected_status_is_lockout():
    d = _decide(_state(status="rejected"), prev=2, pdir=+1, pticks=1)
    assert d.direction == +1


def test_axis_d_ceiling_forbids_paid_spill():
    fc = {
        "axis_prepaid": {"projected_close_pct": 70.0},
        "limits": {"daily": {"remaining_usd": 0.0}},
    }
    d = _decide(_state(weekly_pct=70.0), fc, prev=3)
    assert d.allow_paid_spill is False


# --------------------------------------------------------------------------- #
# End-to-end run_once + overlay file + persistence                              #
# --------------------------------------------------------------------------- #
def test_run_once_writes_overlay_and_persists_hysteresis(tmp_path):
    qs = tmp_path / "quota_state.json"
    qs.write_text(
        json.dumps(
            {
                "weekly_pct": 70.0,
                "weekly_reset": (NOW + timedelta(days=3)).isoformat(),
                "captured_at": NOW.isoformat(),
                "status": "allowed",
            }
        ),
        encoding="utf-8",
    )
    fc = tmp_path / "forecast_latest.json"
    fc.write_text(
        json.dumps({"axis_prepaid": {"projected_close_pct": 70.0}}), encoding="utf-8"
    )
    overlay = tmp_path / "overlay.json"

    # Tick 1: pending, held at neutral 3.
    d1 = ctrl.run_once(
        quota_state_path=qs, forecast_path=fc, overlay_path=overlay, now=NOW
    )
    assert d1.c_to_t_threshold == 3
    assert overlay.is_file()
    saved = json.loads(overlay.read_text(encoding="utf-8"))
    assert saved["_hysteresis"]["pending_dir"] == -1
    assert saved["_hysteresis"]["pending_ticks"] == 1

    # Tick 2: streak persisted via the overlay file -> move to 2.
    d2 = ctrl.run_once(
        quota_state_path=qs, forecast_path=fc, overlay_path=overlay, now=NOW
    )
    assert d2.c_to_t_threshold == 2


def test_gate_reads_overlay_advisory(tmp_path, monkeypatch):
    import importlib.util

    gate_path = _RUNTIME / "router" / "gate.py"
    spec = importlib.util.spec_from_file_location("router.gate", gate_path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    overlay_dir = tmp_path / "07_LOGS_AND_AUDIT" / "control_plane"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "routing_policy_overlay.json").write_text(
        json.dumps({"c_to_t_threshold": 2, "allow_paid_spill": False}),
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "_REPO", tmp_path)
    note = gate._overlay_advisory()
    assert "C->T>=2" in note
    assert "paid_spill=False" in note
