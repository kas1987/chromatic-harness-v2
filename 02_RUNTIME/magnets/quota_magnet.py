"""Quota Magnet — observes the Axis P prepaid-quota inflection points.

The consumer half of the token control plane (TOKEN_ECONOMY_SPEC §7), expressed
as a first-class Magnet instead of a standalone controller script. It WRAPS the
pure control law in :mod:`control_plane.controller` (``compute_decision``) and
maps the resulting :class:`OverlayDecision` onto a :class:`MagnetEvent`, so the
quota loop joins the same orchestrator pipeline as ScopeMagnet / CostMagnet.

Producer/consumer split (the reason this is a Magnet, not a log-watcher):
  * The weekly quota % lives ONLY in the ``anthropic-ratelimit-unified-*``
    response headers — it is in no log. A *producer* (``quota_proxy`` today,
    OTEL/statusline later) captures it into ``quota_state.json``.
  * This Magnet is the *consumer*: at the flow-state inflection points it owns,
    it reads the captured state (+ the already-logged forecast) and emits a
    routing recommendation. It can also *actuate* (persist the overlay the
    router reads) when the signal asks.

Risk semantics are INVERTED (spec §1): under-utilising the prepaid asset is the
tracked variance, but it must NEVER halt a mission — so under-target emits only a
low-grade ``risk_delta`` and a routing ``recommended_action`` that is
deliberately outside the orchestrator's halt/escalate vocabulary. Real risk
(lockout / stale signal) emits a larger — but still sub-halt — delta.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_RUNTIME = _HERE.parent  # 02_RUNTIME
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent  # noqa: E402
from budget.quota_state import (  # noqa: E402
    STALENESS_SECONDS,
    QuotaState,
    QuotaStateReader,
)
from control_plane.controller import (  # noqa: E402
    NEUTRAL_THRESHOLD,
    OverlayDecision,
    compute_decision,
    run_once,
)

# Inflection points where a routing recommendation is meaningful. Everything
# else gets a neutral observation (no spurious risk/confidence deltas).
_ACTIVE_INFLECTIONS = frozenset(
    {"pre_dispatch", "routing_decision", "phase_boundary", "post_execution"}
)

# recommended_action vocabulary — intentionally DISJOINT from the orchestrator's
# halt/escalate set {"halt_and_revert","halt","escalate","review"} so a quota
# nudge can never force a mission halt.
ACTION_SPEND = "route_lower_bar_spend_prepaid"  # dir -1: under target
ACTION_SPILL = "route_raise_bar_spill"  # dir +1 / lockout
ACTION_HOLD = "route_hold"  # deadband / on-track
ACTION_CONSERVATIVE = "route_conservative_hold"  # stale signal


class QuotaMagnet(BaseMagnet):
    name = "quota_magnet"

    def observe(
        self,
        mission_id: str,
        inflection_point: str,
        signal: dict[str, Any],
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)
        if inflection_point not in _ACTIVE_INFLECTIONS:
            return event

        state = self._resolve_state(signal)
        forecast = dict(signal.get("forecast") or {})
        prev = int(signal.get("previous_threshold", NEUTRAL_THRESHOLD))
        pending_dir = int(signal.get("pending_dir", 0))
        pending_ticks = int(signal.get("pending_ticks", 0))
        max_age = int(signal.get("max_age_seconds", STALENESS_SECONDS))

        try:
            decision = compute_decision(
                state,
                forecast,
                previous_threshold=prev,
                pending_dir=pending_dir,
                pending_ticks=pending_ticks,
                max_age_seconds=max_age,
            )
        except Exception:  # noqa: BLE001 — observation must never raise
            return event

        self._apply_decision(event, state, decision)

        # Optional actuation: persist the overlay the router reads. Off by
        # default (a Magnet observes; it actuates only when explicitly asked).
        if signal.get("actuate"):
            try:
                run_once(
                    quota_state_path=signal.get("quota_state_path"),
                    forecast_path=signal.get("forecast_path"),
                    overlay_path=signal.get("overlay_path"),
                    max_age_seconds=max_age,
                )
                event.evidence.append("actuated: routing_policy_overlay persisted")
            except Exception:  # noqa: BLE001 — fail-open
                event.evidence.append("actuation_failed (fail-open)")

        return event

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _resolve_state(signal: dict[str, Any]) -> QuotaState:
        """Build a QuotaState from inline signal (tests) or disk (runtime)."""
        if isinstance(signal.get("quota_state_obj"), QuotaState):
            return signal["quota_state_obj"]
        if isinstance(signal.get("quota_state"), dict):
            return QuotaState.from_dict(signal["quota_state"])
        return QuotaStateReader(
            signal.get("quota_state_path"),
            max_age_seconds=int(signal.get("max_age_seconds", STALENESS_SECONDS)),
        ).read()

    @staticmethod
    def _apply_decision(
        event: MagnetEvent, state: QuotaState, decision: OverlayDecision
    ) -> None:
        event.evidence = list(decision.reasons)
        event.observed_signal = {
            "weekly_pct": state.weekly_pct,
            "session_5h_pct": state.session_5h_pct,
            "c_to_t_threshold": decision.c_to_t_threshold,
            "previous_threshold": decision.previous_threshold,
            "direction": decision.direction,
            "allow_paid_spill": decision.allow_paid_spill,
            "staleness_fallback": decision.staleness_fallback,
            "status": state.status,
        }

        if decision.staleness_fallback:
            event.risk_delta = 0.35
            event.confidence_delta = -3.0
            event.recommended_action = ACTION_CONSERVATIVE
            return

        lockout = (
            decision.direction > 0
            and not decision.deadband_hold
            and (
                (state.status or "").lower()
                in ("rejected", "throttled", "rate_limited")
                or (state.session_5h_pct is not None and state.session_5h_pct >= 90.0)
            )
        )

        if lockout:
            event.risk_delta = 0.45  # real risk, still < 0.5 halt threshold alone
            event.confidence_delta = -2.0
            event.recommended_action = ACTION_SPILL
        elif decision.deadband_hold:
            event.risk_delta = 0.0
            event.confidence_delta = 5.0  # on track to target — healthy
            event.recommended_action = ACTION_HOLD
        elif decision.direction < 0:
            # Under-utilising prepaid: low-grade variance, never a halt.
            event.risk_delta = 0.1
            event.confidence_delta = 2.0
            event.recommended_action = ACTION_SPEND
        else:  # direction > 0 without lockout: easing off an over-shoot
            event.risk_delta = 0.05
            event.confidence_delta = 1.0
            event.recommended_action = ACTION_SPILL
