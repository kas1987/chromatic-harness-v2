"""Validation Magnet — observes the VALIDATION inflection point.

Canonical magnet #5. Collects test results, lint/security findings, evaluates
quality gates, and assembles an evidence bundle. Pairs with ConfidenceMagnet
(which runs the test-pyramid analysis) — this magnet owns the pass/fail gate
signal and the evidence bundle the Agent Lead consumes downstream.
"""

from __future__ import annotations

from typing import Any

from .base_magnet import BaseMagnet, MagnetEvent

_VALIDATION_POINTS = {"validation", "test_results", "tests_complete", "post_execution"}


class ValidationMagnet(BaseMagnet):
    name = "validation_magnet"

    def observe(
        self, mission_id: str, inflection_point: str, signal: dict[str, Any]
    ) -> MagnetEvent:
        event = super().observe(mission_id, inflection_point, signal)
        if inflection_point not in _VALIDATION_POINTS:
            return event

        risk = 0.0
        confidence = 0.0
        evidence: list[str] = []
        gates: dict[str, bool] = {}

        # Test results
        tests = signal.get("tests") or signal.get("test_results")
        if isinstance(tests, dict):
            failed = int(tests.get("failed") or 0)
            passed = int(tests.get("passed") or 0)
            if failed > 0:
                risk += min(0.1 + failed * 0.05, 0.5)
                evidence.append(f"{failed} test(s) failed")
                gates["tests"] = False
            elif passed > 0:
                confidence += 0.06
                evidence.append(f"{passed} test(s) passed")
                gates["tests"] = True

        # Lint gate
        lint = signal.get("lint")
        if isinstance(lint, dict):
            if lint.get("ok") is False or int(lint.get("errors") or 0) > 0:
                risk += 0.1
                evidence.append("Lint errors present")
                gates["lint"] = False
            else:
                confidence += 0.03
                gates["lint"] = True

        # Security gate
        security = signal.get("security")
        if isinstance(security, dict):
            findings = security.get("findings") or []
            if security.get("ok") is False or findings:
                risk += min(0.15 + len(findings) * 0.05, 0.5)
                evidence.append(f"{len(findings)} security finding(s)")
                gates["security"] = False
            else:
                confidence += 0.04
                gates["security"] = True

        # Quality gates summary + evidence bundle
        all_gates_pass = bool(gates) and all(gates.values())
        if gates and all_gates_pass:
            confidence += 0.05
            evidence.append("All quality gates passed")

        event.observed_signal["quality_gates"] = gates
        event.observed_signal["evidence_bundle"] = list(evidence)
        event.observed_signal["validation_passed"] = all_gates_pass if gates else None

        event.risk_delta = round(min(risk, 1.0), 3)
        event.confidence_delta = round(confidence, 3)
        event.evidence = evidence
        if risk >= 0.3:
            event.recommended_action = "replan"
        elif risk >= 0.1:
            event.recommended_action = "review"
        elif gates and all_gates_pass:
            event.recommended_action = "proceed"
        return event
