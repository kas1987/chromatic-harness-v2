"""Base Magnet skeleton."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class MagnetEvent:
    mission_id: str
    magnet_name: str
    inflection_point: str
    observed_signal: dict[str, Any]
    risk_delta: float = 0.0
    confidence_delta: float = 0.0
    evidence: list[str] = field(default_factory=list)
    recommended_action: str = "none"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BaseMagnet:
    name = "base_magnet"

    def observe(self, mission_id: str, inflection_point: str, signal: dict[str, Any]) -> MagnetEvent:
        return MagnetEvent(
            mission_id=mission_id,
            magnet_name=self.name,
            inflection_point=inflection_point,
            observed_signal=signal,
        )
