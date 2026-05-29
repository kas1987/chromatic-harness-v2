"""Closure Magnet — fires when a mission completes or a session closes."""

from .base_magnet import BaseMagnet, MagnetEvent


class ClosureMagnet(BaseMagnet):
    name = "closure_magnet"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)
        if signal.get("validation_passed"):
            event.confidence_delta = 5.0
            event.risk_delta = -0.05
            event.recommended_action = "close_mission"
        elif signal.get("validation_failed"):
            event.risk_delta = 0.2
            event.confidence_delta = -10.0
            event.recommended_action = "replan"
            event.evidence.append("validation_failed")
        else:
            event.recommended_action = "handoff"
        return event
