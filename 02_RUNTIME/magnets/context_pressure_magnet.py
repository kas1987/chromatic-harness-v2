"""Context-Pressure Magnet — event-driven compaction trigger (Gap B).

Closes Gap B of ``docs/operations/SESSION_LIFECYCLE_AUTOMATION_ALIGNMENT.md``:
today, compaction at 50–65% context depends on the agent *noticing* pressure. This
Magnet turns context pressure into a deterministic signal at the inflection points it
owns, mirroring how :class:`QuotaMagnet` watches the prepaid-quota axis — so the
"compact now" decision is made by an event, not by agent vigilance.

Bands (configurable via signal): below ``soft_pct`` (default 50) → hold; ``soft_pct``
to ``hard_pct`` (default 80) → checkpoint compaction; at/above ``hard_pct`` → compact
now. recommended_action is intentionally DISJOINT from the orchestrator's
halt/escalate vocabulary — a compaction nudge must never halt a mission.
"""

from __future__ import annotations

from typing import Any

from .base_magnet import BaseMagnet, MagnetEvent

# Inflection points where a compaction recommendation is meaningful.
_ACTIVE_INFLECTIONS = frozenset(
    {"pre_dispatch", "phase_boundary", "post_execution", "turn_boundary"}
)

ACTION_HOLD = "context_hold"
ACTION_CHECKPOINT = "compact_checkpoint"
ACTION_NOW = "compact_now"

_DEFAULT_SOFT = 50.0
_DEFAULT_HARD = 80.0


def _pct(signal: dict[str, Any]) -> float | None:
    """Resolve context-pressure percent from an explicit pct or used/window tokens."""
    if signal.get("context_pct") is not None:
        try:
            return float(signal["context_pct"])
        except (TypeError, ValueError):
            return None
    used = signal.get("used_tokens")
    window = signal.get("window_tokens")
    try:
        used_f = float(used)
        window_f = float(window)
    except (TypeError, ValueError):
        return None
    if window_f <= 0:
        return None
    return max(0.0, min(100.0, used_f / window_f * 100.0))


class ContextPressureMagnet(BaseMagnet):
    name = "context_pressure_magnet"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict[str, Any]
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)
        if inflection_point not in _ACTIVE_INFLECTIONS:
            return event

        pct = _pct(signal)
        if pct is None:
            event.evidence.append("context pressure unknown (no pct/tokens)")
            return event

        soft = float(signal.get("soft_pct", _DEFAULT_SOFT))
        hard = float(signal.get("hard_pct", _DEFAULT_HARD))
        event.observed_signal = {
            "context_pct": round(pct, 2),
            "soft_pct": soft,
            "hard_pct": hard,
        }

        if pct >= hard:
            event.risk_delta = 0.4
            event.confidence_delta = -3.0
            event.recommended_action = ACTION_NOW
            event.evidence.append(
                f"context {pct:.0f}% ≥ hard {hard:.0f}% — compact now"
            )
        elif pct >= soft:
            event.risk_delta = 0.15
            event.confidence_delta = -1.0
            event.recommended_action = ACTION_CHECKPOINT
            event.evidence.append(
                f"context {pct:.0f}% in [{soft:.0f}%,{hard:.0f}%) — checkpoint compaction"
            )
        else:
            event.recommended_action = ACTION_HOLD
            event.evidence.append(f"context {pct:.0f}% < soft {soft:.0f}% — hold")
        return event
