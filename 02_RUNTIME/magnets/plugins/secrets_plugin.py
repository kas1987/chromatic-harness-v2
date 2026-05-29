"""Example domain plugin: surface secret-scan hits without editing core magnets."""

from __future__ import annotations

from typing import Any

from ..base_magnet import MagnetEvent
from ..plugin import MagnetPlugin


class SecretsSurfacePlugin(MagnetPlugin):
    name = "secrets_surface_plugin"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict[str, Any]
    ) -> MagnetEvent:
        hits = signal.get("secrets_detected") or signal.get("secret_hits") or []
        evidence: list[str] = []
        risk_delta = 0.0
        confidence_delta = 0.0
        recommended_action = "none"

        if hits:
            count = len(hits) if isinstance(hits, list) else 1
            evidence.append(f"Secrets scan: {count} hit(s) detected")
            risk_delta = min(0.4, 0.1 * count)
            confidence_delta = -0.15
            recommended_action = "halt" if count > 0 else "review"

        return MagnetEvent(
            mission_id=mission_id,
            magnet_name=self.name,
            inflection_point=inflection_point,
            observed_signal=signal,
            risk_delta=risk_delta,
            confidence_delta=confidence_delta,
            evidence=evidence,
            recommended_action=recommended_action,
        )
