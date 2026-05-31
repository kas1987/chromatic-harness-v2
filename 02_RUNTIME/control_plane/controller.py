"""Proportional quota controller with deadband + hysteresis (B7).

Per TOKEN_ECONOMY_SPEC §7. Closes the loop between the Axis P prepaid signal
and the router by emitting a *dynamic C->T threshold overlay*. The overlay is
the single knob the router reads to decide how aggressively to spend the
prepaid weekly quota vs. spill to local / cheapest API.

Doctrine (spec §1, §7) — the risk semantics are **inverted**: the prepaid
weekly Claude quota is a depleting asset with a ``>=90%`` utilization target, so
*under*-use is the tracked variance.

Control law (proportional, around the 90% setpoint):
  * **Deadband** of +/-``DEADBAND_PCT`` around the 90% target — inside it the
    controller leaves the threshold alone (prevents jitter from rounding noise).
  * **Projected close < 90% near reset** -> *lower* the C->T bar so C3/C4 route
    to ``native_claude`` (spend the prepaid asset before it resets to nothing).
  * **5h / 7d lockout risk** (near a window reset or status == ``rejected``) ->
    *raise* the bar, spilling C1/C2 to local then the cheapest API so we do not
    burn the last of a window and get locked out.
  * **Axis D ($) caps** are a hard ceiling regardless: if the daily/monthly $
    budget is exhausted the overlay forbids spilling to paid API providers.

Anti-oscillation:
  * **Hysteresis / rate limiting** — the integer C->T threshold may move at most
    ``MAX_STEP_PER_TICK`` level per tick, and only after the proportional signal
    has pointed the same direction for ``HYSTERESIS_TICKS`` consecutive ticks.
    The persistent tick counters live in the overlay file itself, so the
    rate-limit survives across process invocations (the controller runs as a
    short-lived scheduler job, not a daemon).

Staleness (spec §7, §10):
  * A **5-minute staleness guard** on the Axis P signal. If ``quota_state.json``
    is missing / malformed / older than ``STALENESS_SECONDS`` the controller does
    NOT trust it — it emits a **conservative fallback** overlay (raise the bar,
    forbid paid spill) so a dead proxy can never trick us into over-spending.

The controller never raises and never blocks the request path: it only writes a
JSON file that ``gate.py`` reads fail-open.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Self-contained loader (mirrors gate.py): works as script or module ──────
_CONTROL_DIR = Path(__file__).resolve().parent
_RUNTIME_DIR = _CONTROL_DIR.parent  # 02_RUNTIME
_REPO = _RUNTIME_DIR.parent

for _p in (str(_RUNTIME_DIR), str(_REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from budget.quota_state import (  # noqa: E402
    MANUAL_SEED_TTL_SECONDS,
    STALENESS_SECONDS,
    QuotaState,
    QuotaStateReader,
)

# ── Tunables ────────────────────────────────────────────────────────────────
TARGET_PCT = 90.0  # reuse the canonical setpoint (spec §1, agent_budget.yaml)
DEADBAND_PCT = 2.0  # +/- around target where no move is made
HYSTERESIS_TICKS = 2  # consecutive same-direction ticks before a move
MAX_STEP_PER_TICK = 1  # max C-level threshold move per tick (rate limit)

# C->T threshold is the lowest complexity level that is allowed to route to the
# prepaid native_claude lane. Lower bar => MORE work spent on prepaid quota.
#   threshold == 1  -> even C1 may use native_claude (max prepaid spend)
#   threshold == 4  -> only C4 may use native_claude (min prepaid spend)
C_MIN, C_MAX = 1, 4
NEUTRAL_THRESHOLD = 3  # balanced default / cold-start

# Window reset proximity that counts as "near reset" / lockout risk (hours).
RESET_NEAR_HOURS_7D = 24.0
RESET_NEAR_HOURS_5H = 0.5

# Output location (spec §7).
DEFAULT_OVERLAY_PATH = (
    _REPO / "07_LOGS_AND_AUDIT" / "control_plane" / "routing_policy_overlay.json"
)
DEFAULT_FORECAST_PATH = _REPO / "07_LOGS_AND_AUDIT" / "budget" / "forecast_latest.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _hours_until(reset: Any, *, now: datetime) -> float | None:
    dt = _parse_ts(reset)
    if dt is None:
        return None
    return (dt - now).total_seconds() / 3600.0


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


# ─────────────────────────────────────────────────────────────────────────── #
@dataclass
class OverlayDecision:
    """The computed overlay + the rationale (audited)."""

    c_to_t_threshold: int
    previous_threshold: int
    direction: int  # -1 lower bar (spend prepaid), 0 hold, +1 raise bar (spill)
    allow_paid_spill: bool
    staleness_fallback: bool
    deadband_hold: bool
    reasons: list[str] = field(default_factory=list)
    # persistent hysteresis counters (carried in the overlay file)
    pending_dir: int = 0
    pending_ticks: int = 0

    @property
    def changed(self) -> bool:
        return self.c_to_t_threshold != self.previous_threshold

    def to_overlay(self, *, now: datetime) -> dict[str, Any]:
        return {
            "schema": "routing_policy_overlay/v1",
            "generated_at": now.isoformat().replace("+00:00", "Z"),
            "c_to_t_threshold": self.c_to_t_threshold,
            "allow_paid_spill": self.allow_paid_spill,
            "staleness_fallback": self.staleness_fallback,
            "deadband_hold": self.deadband_hold,
            "direction": self.direction,
            "target_pct": TARGET_PCT,
            "deadband_pct": DEADBAND_PCT,
            "reasons": self.reasons,
            # persistent hysteresis state (read back on the next tick)
            "_hysteresis": {
                "previous_threshold": self.c_to_t_threshold,
                "pending_dir": self.pending_dir,
                "pending_ticks": self.pending_ticks,
            },
        }


def _read_overlay_state(path: Path) -> tuple[int, int, int]:
    """Return (previous_threshold, pending_dir, pending_ticks). Fail-open."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        hy = data.get("_hysteresis") or {}
        prev = int(
            hy.get(
                "previous_threshold", data.get("c_to_t_threshold", NEUTRAL_THRESHOLD)
            )
        )
        return (
            _clamp(prev, C_MIN, C_MAX),
            int(hy.get("pending_dir", 0)),
            int(hy.get("pending_ticks", 0)),
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return NEUTRAL_THRESHOLD, 0, 0


def _read_forecast(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _axis_d_exhausted(forecast: dict[str, Any]) -> bool:
    """True when the Axis D ($) hard ceiling is hit (daily or monthly)."""
    limits = forecast.get("limits") or {}
    for window in ("daily", "monthly"):
        w = limits.get(window) or {}
        remaining = w.get("remaining_usd")
        if remaining is not None:
            try:
                if float(remaining) <= 0.0:
                    return True
            except (TypeError, ValueError):
                pass
    fc = forecast.get("forecast") or {}
    if fc.get("daily_over_cap") or fc.get("monthly_over_cap"):
        return True
    return False


# ─────────────────────────────────────────────────────────────────────────── #
def compute_decision(
    state: QuotaState,
    forecast: dict[str, Any],
    *,
    previous_threshold: int,
    pending_dir: int,
    pending_ticks: int,
    now: datetime | None = None,
    max_age_seconds: int = STALENESS_SECONDS,
) -> OverlayDecision:
    """Pure control law. No I/O — fully unit-testable with mock inputs."""
    now = now or _now()
    prev = _clamp(previous_threshold, C_MIN, C_MAX)
    reasons: list[str] = []

    # ── Staleness guard (spec §7): never trust a dead/stale proxy ───────────
    if not state.is_fresh(max_age_seconds=max_age_seconds, now=now):
        reasons.append(
            "staleness_fallback: Axis P signal missing/stale (>"
            f"{max_age_seconds}s) -> conservative (raise bar, forbid paid spill)"
        )
        # Conservative: raise the bar toward C_MAX (do not over-spend prepaid on
        # an unverified signal) and forbid paid spill (do not burn $ blindly).
        target = _clamp(prev + MAX_STEP_PER_TICK, C_MIN, C_MAX)
        return OverlayDecision(
            c_to_t_threshold=target,
            previous_threshold=prev,
            direction=+1 if target > prev else 0,
            allow_paid_spill=False,
            staleness_fallback=True,
            deadband_hold=False,
            reasons=reasons,
            pending_dir=0,
            pending_ticks=0,
        )

    weekly_pct = state.weekly_pct
    # axis_prepaid (B6) is the projected close; prefer it over the raw %.
    axis = forecast.get("axis_prepaid") or {}
    projected = axis.get("projected_close_pct")
    if projected is None:
        projected = weekly_pct
    setpoint_value = projected if projected is not None else weekly_pct

    # ── Window lockout risk (honor BOTH 5h and 7d) ──────────────────────────
    hrs_7d = _hours_until(state.weekly_reset, now=now)
    hrs_5h = _hours_until(state.session_5h_reset, now=now)
    near_7d_reset = hrs_7d is not None and 0.0 <= hrs_7d <= RESET_NEAR_HOURS_7D
    near_5h_reset = hrs_5h is not None and 0.0 <= hrs_5h <= RESET_NEAR_HOURS_5H
    status = (state.status or "").lower()
    lockout_risk = status in ("rejected", "throttled", "rate_limited") or (
        near_5h_reset
        and (state.session_5h_pct is not None and state.session_5h_pct >= 90.0)
    )

    allow_paid_spill = True
    desired_dir = 0  # -1 lower bar, +1 raise bar, 0 hold

    # Axis D hard ceiling overrides spill permission regardless of Axis P.
    if _axis_d_exhausted(forecast):
        allow_paid_spill = False
        reasons.append("axis_d_hard_ceiling: $ cap exhausted -> forbid paid spill")

    if lockout_risk:
        desired_dir = +1
        reasons.append(
            "lockout_risk: 5h/7d window near limit -> raise C->T bar, "
            "spill C1/C2 to local then cheapest API"
        )
        # Spilling to local is always fine; paid spill only if $ allows.
    elif setpoint_value is None:
        # Fresh record but no usable %: hold (rare).
        reasons.append("no_setpoint: fresh signal without weekly_pct -> hold")
    else:
        delta = TARGET_PCT - float(setpoint_value)  # >0 => under target
        if abs(delta) <= DEADBAND_PCT:
            desired_dir = 0
            reasons.append(
                f"deadband: |projected {setpoint_value:.2f} - target "
                f"{TARGET_PCT:.1f}| <= {DEADBAND_PCT:.1f} -> hold"
            )
        elif delta > 0:
            # Under-utilizing the prepaid asset -> lower the bar to spend it.
            desired_dir = -1
            msg = (
                f"under_target: projected {setpoint_value:.2f} < {TARGET_PCT:.1f} "
                "-> lower C->T bar (route C3/C4 to native_claude)"
            )
            if near_7d_reset:
                msg += " [near 7d reset: spend before it resets]"
            reasons.append(msg)
        else:
            # Over target (rare for prepaid) -> raise the bar / ease off.
            desired_dir = +1
            reasons.append(
                f"over_target: projected {setpoint_value:.2f} > {TARGET_PCT:.1f} "
                "-> raise C->T bar"
            )

    # ── Deadband hold short-circuits any move ───────────────────────────────
    if desired_dir == 0:
        return OverlayDecision(
            c_to_t_threshold=prev,
            previous_threshold=prev,
            direction=0,
            allow_paid_spill=allow_paid_spill,
            staleness_fallback=False,
            deadband_hold=True,
            reasons=reasons,
            pending_dir=0,
            pending_ticks=0,
        )

    # ── Hysteresis / rate limiting (anti-oscillation) ───────────────────────
    if desired_dir == pending_dir:
        ticks = pending_ticks + 1
    else:
        ticks = 1  # direction flipped: reset the streak
    if ticks >= HYSTERESIS_TICKS:
        step = desired_dir * MAX_STEP_PER_TICK
        new_threshold = _clamp(prev + step, C_MIN, C_MAX)
        # Move consumed the streak — reset counters.
        new_pending_dir, new_pending_ticks = 0, 0
        if new_threshold == prev:
            reasons.append("rate_limit: at C-level bound, no further move")
        else:
            reasons.append(
                f"hysteresis_satisfied: {ticks} consecutive ticks dir="
                f"{desired_dir:+d} -> move threshold {prev}->{new_threshold}"
            )
    else:
        new_threshold = prev
        new_pending_dir, new_pending_ticks = desired_dir, ticks
        reasons.append(
            f"hysteresis_pending: dir={desired_dir:+d} tick {ticks}/"
            f"{HYSTERESIS_TICKS} -> hold (anti-oscillation)"
        )

    return OverlayDecision(
        c_to_t_threshold=new_threshold,
        previous_threshold=prev,
        direction=desired_dir,
        allow_paid_spill=allow_paid_spill,
        staleness_fallback=False,
        deadband_hold=False,
        reasons=reasons,
        pending_dir=new_pending_dir,
        pending_ticks=new_pending_ticks,
    )


def _audit_overlay_change(decision: OverlayDecision, overlay: dict[str, Any]) -> None:
    """Log every overlay change to the routes audit (spec §7). Fail-open."""
    try:
        from audit.two_log import TwoLogAudit  # type: ignore[import]

        audit = TwoLogAudit(_REPO)
        audit.append_execution(
            {
                "event_type": "control_plane.overlay",
                "agent_role": "controller",
                "task_id": "quota_control",
                "c_to_t_threshold": decision.c_to_t_threshold,
                "previous_threshold": decision.previous_threshold,
                "direction": decision.direction,
                "allow_paid_spill": decision.allow_paid_spill,
                "staleness_fallback": decision.staleness_fallback,
                "reason": "; ".join(decision.reasons),
            }
        )
    except Exception:  # noqa: BLE001 — audit never blocks the control loop
        pass
    # Mirror to the daily routing log so backtests reconcile overlay moves with
    # the routes_*.jsonl decisions they influenced (spec §7).
    try:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        log = _REPO / "07_LOGS_AND_AUDIT" / "routing" / f"routes_{today}.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "timestamp": overlay["generated_at"],
                        "event_type": "control_plane.overlay_change",
                        "c_to_t_threshold": decision.c_to_t_threshold,
                        "previous_threshold": decision.previous_threshold,
                        "direction": decision.direction,
                        "allow_paid_spill": decision.allow_paid_spill,
                        "staleness_fallback": decision.staleness_fallback,
                        "reasons": decision.reasons,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception:  # noqa: BLE001
        pass


def run_once(
    *,
    quota_state_path: Path | str | None = None,
    forecast_path: Path | str | None = None,
    overlay_path: Path | str | None = None,
    now: datetime | None = None,
    max_age_seconds: int = STALENESS_SECONDS,
) -> OverlayDecision:
    """Read inputs, compute the overlay, persist it, audit changes. Fail-open."""
    now = now or _now()
    overlay_path = Path(overlay_path) if overlay_path else DEFAULT_OVERLAY_PATH
    forecast_path = Path(forecast_path) if forecast_path else DEFAULT_FORECAST_PATH

    state = QuotaStateReader(quota_state_path, max_age_seconds=max_age_seconds).read()
    forecast = _read_forecast(forecast_path)
    prev, pending_dir, pending_ticks = _read_overlay_state(overlay_path)

    # Manual-seeded quota state is valid for 24h (MANUAL_SEED_TTL_SECONDS);
    # proxy-captured state expires in the standard 5-minute window.
    effective_max_age = (
        MANUAL_SEED_TTL_SECONDS
        if state.source == "manual"
        else max_age_seconds
    )

    decision = compute_decision(
        state,
        forecast,
        previous_threshold=prev,
        pending_dir=pending_dir,
        pending_ticks=pending_ticks,
        now=now,
        max_age_seconds=effective_max_age,
    )

    overlay = decision.to_overlay(now=now)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.write_text(
        json.dumps(overlay, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if decision.changed or decision.staleness_fallback:
        _audit_overlay_change(decision, overlay)

    return decision


def main() -> None:
    decision = run_once()
    sys.stdout.write(
        f"controller: c_to_t_threshold={decision.c_to_t_threshold} "
        f"(was {decision.previous_threshold}) dir={decision.direction:+d} "
        f"paid_spill={decision.allow_paid_spill} "
        f"stale={decision.staleness_fallback}\n"
    )


if __name__ == "__main__":
    main()
