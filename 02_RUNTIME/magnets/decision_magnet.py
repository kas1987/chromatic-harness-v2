"""Decision Magnet — observes the DECIDE & CONTINUE inflection point.

Canonical magnet #6. Aggregates the confidence score and risk assessment into a
continuation decision using the CMP confidence-gate bands, and suggests the next
step. This is the single magnet that maps a composite score onto the diagram's
gate bands:

    90-100%  -> proceed (auto)
    70-89%   -> proceed_reversible_only
    50-69%   -> caution / self_heal
     0-49%   -> escalate / replan
"""

from __future__ import annotations

from typing import Any

from .base_magnet import BaseMagnet, MagnetEvent

_DECISION_POINTS = {"decision", "decide", "post_validation", "score_validate"}


def decide_band(confidence_score: float) -> tuple[str, str]:
    """Map a 0-100 confidence score to (action, next_step) per CMP gate bands."""
    if confidence_score >= 90:
        return "proceed", "auto_proceed_to_next_objective"
    if confidence_score >= 70:
        return "proceed_reversible_only", "proceed_with_reversible_actions"
    if confidence_score >= 50:
        return "self_heal", "attempt_self_heal_then_recheck"
    return "escalate", "escalate_or_replan"


class DecisionMagnet(BaseMagnet):
    name = "decision_magnet"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict[str, Any]
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)
        if inflection_point not in _DECISION_POINTS:
            return event

        confidence_score = _as_float(signal.get("confidence_score"), default=75.0)
        risk_score = _as_float(signal.get("risk_score"), default=0.0)

        # Risk override — a high risk score forces escalation regardless of confidence
        if risk_score >= 0.5:
            action, next_step = "escalate", "escalate_high_risk"
        else:
            action, next_step = decide_band(confidence_score)

        evidence = [
            f"confidence_score={confidence_score:.1f}",
            f"risk_score={risk_score:.2f}",
            f"band_action={action}",
        ]

        event.observed_signal["decision"] = action
        event.observed_signal["next_step"] = next_step
        event.observed_signal["confidence_score"] = confidence_score
        event.observed_signal["risk_score"] = risk_score
        event.evidence = evidence
        event.recommended_action = action
        # Nudge composite confidence/risk so the orchestrator reflects the decision
        if action == "proceed":
            event.confidence_delta = 2.0
        elif action in ("escalate",):
            event.risk_delta = 0.1
            event.confidence_delta = -5.0
        return event


def _as_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
