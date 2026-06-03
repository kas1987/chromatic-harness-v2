"""Tests for magnets.validation_magnet — ValidationMagnet."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.validation_magnet import ValidationMagnet

_VALIDATION_POINTS = ["validation", "test_results", "tests_complete", "post_execution"]


class TestValidationMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(ValidationMagnet, BaseMagnet)

    def test_name(self):
        assert ValidationMagnet.name == "validation_magnet"

    def test_observe_returns_magnet_event(self):
        event = ValidationMagnet().observe("m1", "validation", {})
        assert isinstance(event, MagnetEvent)


class TestValidationMagnetNonValidationInflection:
    def test_non_validation_inflection_no_delta(self):
        event = ValidationMagnet().observe("m1", "intake", {"tests": {"passed": 5}})
        assert event.risk_delta == 0.0

    def test_non_validation_inflection_default_action(self):
        event = ValidationMagnet().observe("m1", "dispatch", {})
        assert event.recommended_action == "none"


class TestValidationMagnetTestResults:
    def test_failed_tests_raise_risk(self):
        event = ValidationMagnet().observe("m1", "validation", {"tests": {"passed": 10, "failed": 2}})
        assert event.risk_delta > 0

    def test_failed_tests_gate_false(self):
        event = ValidationMagnet().observe("m1", "validation", {"tests": {"passed": 10, "failed": 2}})
        assert event.observed_signal["quality_gates"]["tests"] is False

    def test_failed_tests_validation_not_passed(self):
        event = ValidationMagnet().observe("m1", "validation", {"tests": {"passed": 10, "failed": 2}})
        assert event.observed_signal["validation_passed"] is False

    def test_passed_tests_add_confidence(self):
        event = ValidationMagnet().observe("m1", "validation", {"tests": {"passed": 10, "failed": 0}})
        assert event.confidence_delta > 0

    def test_passed_tests_gate_true(self):
        event = ValidationMagnet().observe("m1", "validation", {"tests": {"passed": 10, "failed": 0}})
        assert event.observed_signal["quality_gates"]["tests"] is True

    def test_zero_passed_zero_failed_no_gate(self):
        """With no tests at all, tests gate should not be set."""
        event = ValidationMagnet().observe("m1", "validation", {"tests": {}})
        assert "tests" not in event.observed_signal["quality_gates"]

    def test_many_failures_capped_risk(self):
        event = ValidationMagnet().observe("m1", "validation", {"tests": {"passed": 0, "failed": 100}})
        assert event.risk_delta <= 1.0

    def test_failure_evidence_message(self):
        event = ValidationMagnet().observe("m1", "validation", {"tests": {"passed": 5, "failed": 3}})
        assert any("3 test(s) failed" in e for e in event.evidence)


class TestValidationMagnetLintGate:
    def test_lint_errors_raise_risk(self):
        event = ValidationMagnet().observe("m1", "validation", {"lint": {"ok": False, "errors": 3}})
        assert event.risk_delta > 0
        assert event.observed_signal["quality_gates"]["lint"] is False

    def test_lint_ok_adds_confidence(self):
        event = ValidationMagnet().observe("m1", "validation", {"lint": {"ok": True}})
        assert event.confidence_delta > 0
        assert event.observed_signal["quality_gates"]["lint"] is True

    def test_lint_ok_false_no_errors_field(self):
        event = ValidationMagnet().observe("m1", "validation", {"lint": {"ok": False}})
        assert event.observed_signal["quality_gates"]["lint"] is False


class TestValidationMagnetSecurityGate:
    def test_security_findings_raise_risk(self):
        event = ValidationMagnet().observe("m1", "validation", {"security": {"ok": False, "findings": ["CVE-123"]}})
        assert event.risk_delta > 0
        assert event.observed_signal["quality_gates"]["security"] is False

    def test_clean_security_adds_confidence(self):
        event = ValidationMagnet().observe("m1", "validation", {"security": {"ok": True, "findings": []}})
        assert event.confidence_delta > 0
        assert event.observed_signal["quality_gates"]["security"] is True

    def test_multiple_findings_increase_risk(self):
        event_1 = ValidationMagnet().observe("m1", "validation", {"security": {"ok": False, "findings": ["f1"]}})
        event_3 = ValidationMagnet().observe(
            "m1", "validation", {"security": {"ok": False, "findings": ["f1", "f2", "f3"]}}
        )
        assert event_3.risk_delta > event_1.risk_delta

    def test_security_findings_capped_at_0_5(self):
        findings = [f"CVE-{i}" for i in range(100)]
        event = ValidationMagnet().observe("m1", "validation", {"security": {"ok": False, "findings": findings}})
        assert event.risk_delta <= 1.0


class TestValidationMagnetAllGatesPass:
    def _all_pass_signal(self):
        return {
            "tests": {"passed": 10, "failed": 0},
            "lint": {"ok": True},
            "security": {"ok": True, "findings": []},
        }

    def test_all_gates_pass_validation_passed_true(self):
        event = ValidationMagnet().observe("m1", "validation", self._all_pass_signal())
        assert event.observed_signal["validation_passed"] is True

    def test_all_gates_pass_proceed_action(self):
        event = ValidationMagnet().observe("m1", "validation", self._all_pass_signal())
        assert event.recommended_action == "proceed"

    def test_all_gates_pass_evidence_contains_all_passed(self):
        event = ValidationMagnet().observe("m1", "validation", self._all_pass_signal())
        assert any("All quality gates passed" in e for e in event.evidence)

    def test_all_gates_pass_no_risk(self):
        event = ValidationMagnet().observe("m1", "validation", self._all_pass_signal())
        assert event.risk_delta == 0.0


class TestValidationMagnetRecommendedActions:
    def test_high_risk_recommends_replan(self):
        # Multiple failures -> risk >= 0.3
        event = ValidationMagnet().observe(
            "m1",
            "validation",
            {
                "tests": {"passed": 0, "failed": 5},
                "lint": {"ok": False},
                "security": {"ok": False, "findings": ["f1"]},
            },
        )
        assert event.recommended_action == "replan"

    def test_medium_risk_recommends_review(self):
        event = ValidationMagnet().observe(
            "m1",
            "validation",
            {"tests": {"passed": 5, "failed": 1}},
        )
        assert event.recommended_action in ("review", "replan")

    def test_all_points_active(self):
        for pt in _VALIDATION_POINTS:
            event = ValidationMagnet().observe("m1", pt, {"tests": {"passed": 5, "failed": 1}})
            assert event.risk_delta > 0, f"expected risk for {pt}"


class TestValidationMagnetEvidenceBundle:
    def test_evidence_bundle_in_signal(self):
        event = ValidationMagnet().observe("m1", "validation", {"tests": {"passed": 5, "failed": 0}})
        assert "evidence_bundle" in event.observed_signal

    def test_evidence_bundle_matches_evidence_list(self):
        event = ValidationMagnet().observe(
            "m1",
            "validation",
            {"tests": {"passed": 5, "failed": 2}, "lint": {"ok": False}},
        )
        bundle = event.observed_signal["evidence_bundle"]
        assert set(event.evidence) == set(bundle)

    def test_validation_passed_none_when_no_gates(self):
        """With no gate data in signal, validation_passed should be None."""
        event = ValidationMagnet().observe("m1", "validation", {})
        assert event.observed_signal["validation_passed"] is None
