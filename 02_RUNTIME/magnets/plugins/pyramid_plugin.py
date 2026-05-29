"""Test pyramid checks as a registerable magnet plugin."""

from __future__ import annotations

from typing import Any

from ..base_magnet import MagnetEvent
from ..plugin import MagnetPlugin
from ..test_pyramid import analyze_test_pyramid


class PyramidCheckPlugin(MagnetPlugin):
    name = "pyramid_check_plugin"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict[str, Any]
    ) -> MagnetEvent:
        evidence: list[str] = []
        risk_delta = 0.0
        confidence_delta = 0.0
        recommended_action = "none"
        observed = dict(signal)

        tests = signal.get("tests") or signal.get("test_results")
        if inflection_point in ("test_results", "tests_complete", "validation") and tests:
            pyramid = analyze_test_pyramid(tests)
            observed["test_pyramid"] = pyramid
            evidence.extend(pyramid["warnings"])
            if pyramid["max_deviation"] >= 0.25:
                risk_delta = 0.05
                confidence_delta = -0.08
                recommended_action = "review"
            elif pyramid["max_deviation"] >= 0.15:
                confidence_delta = -0.03

        return MagnetEvent(
            mission_id=mission_id,
            magnet_name=self.name,
            inflection_point=inflection_point,
            observed_signal=observed,
            risk_delta=risk_delta,
            confidence_delta=confidence_delta,
            evidence=evidence,
            recommended_action=recommended_action,
        )
