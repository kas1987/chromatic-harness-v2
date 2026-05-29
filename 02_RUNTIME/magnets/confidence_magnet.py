"""Confidence magnet with test pyramid validation."""

from __future__ import annotations

from typing import Any

from .base_magnet import BaseMagnet, MagnetEvent
from .test_pyramid import analyze_test_pyramid


class ConfidenceMagnet(BaseMagnet):
    name = "confidence_magnet"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict[str, Any]
    ) -> MagnetEvent:
        confidence_delta = float(signal.get("confidence_delta", 0.0))
        risk_delta = float(signal.get("risk_delta", 0.0))
        evidence: list[str] = list(signal.get("evidence", []))
        recommended_action = signal.get("recommended_action", "none")

        tests = signal.get("tests") or signal.get("test_results")
        if inflection_point in ("test_results", "tests_complete", "validation") and tests:
            pyramid = analyze_test_pyramid(tests)
            signal = {**signal, "test_pyramid": pyramid}
            for warning in pyramid["warnings"]:
                evidence.append(warning)
            if pyramid["max_deviation"] >= 0.25:
                confidence_delta -= 0.08
                risk_delta += 0.05
                if recommended_action == "none":
                    recommended_action = "review"
            elif pyramid["max_deviation"] >= 0.15:
                confidence_delta -= 0.03

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
