"""Closure Magnet — fires when a mission completes or a session closes."""

from .base_magnet import BaseMagnet, MagnetEvent
from .ship_completion import check_ship_completion


class ClosureMagnet(BaseMagnet):
    name = "closure_magnet"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)
        if signal.get("validation_passed"):
            # /ship-idea Stages 8 (lean) + 10 (live) are non-skippable. When ship
            # evidence is present but incomplete, refuse to close and require replan
            # — this binds session exit to the ship-idea completion contract (Gap C).
            ship = check_ship_completion(signal)
            event.observed_signal["ship_completion"] = ship
            if ship["applicable"] and not ship["complete"]:
                event.confidence_delta = -8.0
                event.risk_delta = 0.15
                event.recommended_action = "replan"
                event.evidence.append("ship_incomplete:" + ",".join(ship["missing"]))
                return event
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
