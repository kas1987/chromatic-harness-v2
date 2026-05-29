"""Intake Magnet — fires when a mission or goal arrives."""

from .base_magnet import BaseMagnet, MagnetEvent


class IntakeMagnet(BaseMagnet):
    name = "intake_magnet"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)
        objective = str(signal.get("objective", ""))
        if len(objective) < 10:
            event.risk_delta = 0.1
            event.confidence_delta = -5.0
            event.recommended_action = "clarify_intent"
            event.evidence.append("objective_too_short")
        elif len(objective) > 500:
            event.risk_delta = 0.05
            event.recommended_action = "decompose"
            event.evidence.append("objective_oversized")
        else:
            event.confidence_delta = 2.0
            event.recommended_action = "proceed"
        return event
