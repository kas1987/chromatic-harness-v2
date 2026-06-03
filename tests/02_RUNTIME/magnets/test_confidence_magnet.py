"""Tests for magnets.confidence_magnet — ConfidenceMagnet."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.confidence_magnet import ConfidenceMagnet


class TestConfidenceMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(ConfidenceMagnet, BaseMagnet)

    def test_name(self):
        assert ConfidenceMagnet.name == "confidence_magnet"

    def test_observe_returns_magnet_event(self):
        m = ConfidenceMagnet()
        event = m.observe("m1", "generic", {"confidence_delta": 1.0})
        assert isinstance(event, MagnetEvent)


class TestConfidenceMagnetSignalPassthrough:
    def _observe(self, inflection_point: str, signal: dict) -> MagnetEvent:
        return ConfidenceMagnet().observe("m1", inflection_point, signal)

    def test_passthrough_confidence_delta(self):
        event = self._observe("generic", {"confidence_delta": 3.5})
        assert event.confidence_delta == 3.5

    def test_passthrough_risk_delta(self):
        event = self._observe("generic", {"risk_delta": 0.2})
        assert event.risk_delta == 0.2

    def test_passthrough_evidence(self):
        event = self._observe("generic", {"evidence": ["e1", "e2"]})
        assert "e1" in event.evidence
        assert "e2" in event.evidence

    def test_passthrough_recommended_action(self):
        event = self._observe("generic", {"recommended_action": "review"})
        assert event.recommended_action == "review"

    def test_missing_deltas_default_to_zero(self):
        event = self._observe("generic", {})
        assert event.confidence_delta == 0.0
        assert event.risk_delta == 0.0


class TestConfidenceMagnetPyramidIntegration:
    """Test that the test-pyramid analysis is triggered at the right inflection points."""

    _PYRAMID_POINTS = ["test_results", "tests_complete", "validation"]
    _NON_PYRAMID_POINTS = ["intake", "dispatch", "post_execution_other"]

    def _balanced_tests(self):
        """Return a balanced pyramid: 70% unit, 20% integration, 10% e2e."""
        tests = [{"layer": "unit"} for _ in range(7)]
        tests += [{"layer": "integration"} for _ in range(2)]
        tests += [{"layer": "e2e"} for _ in range(1)]
        return tests

    def _all_unit_tests(self, count=10):
        """Return 100% unit tests — heavy imbalance."""
        return [{"layer": "unit"} for _ in range(count)]

    def test_pyramid_analysis_triggered_at_test_results(self):
        tests = self._balanced_tests()
        event = ConfidenceMagnet().observe("m1", "test_results", {"tests": tests})
        assert "test_pyramid" in event.observed_signal

    def test_pyramid_analysis_triggered_at_tests_complete(self):
        tests = self._balanced_tests()
        event = ConfidenceMagnet().observe("m1", "tests_complete", {"tests": tests})
        assert "test_pyramid" in event.observed_signal

    def test_pyramid_analysis_triggered_at_validation(self):
        tests = self._balanced_tests()
        event = ConfidenceMagnet().observe("m1", "validation", {"test_results": tests})
        assert "test_pyramid" in event.observed_signal

    def test_no_pyramid_analysis_at_non_pyramid_point(self):
        tests = self._balanced_tests()
        event = ConfidenceMagnet().observe("m1", "intake", {"tests": tests})
        assert "test_pyramid" not in event.observed_signal

    def test_severe_imbalance_reduces_confidence(self):
        # 100% unit — max deviation from 70% target is 30% (e2e and integration both off)
        tests = self._all_unit_tests(10)
        base_event = ConfidenceMagnet().observe("m1", "generic", {})
        pyramid_event = ConfidenceMagnet().observe("m1", "test_results", {"tests": tests})
        # With max_deviation >= 0.25, confidence_delta decreases by 0.08
        assert pyramid_event.confidence_delta < base_event.confidence_delta

    def test_severe_imbalance_raises_risk(self):
        tests = self._all_unit_tests(10)
        event = ConfidenceMagnet().observe("m1", "test_results", {"tests": tests})
        assert event.risk_delta > 0.0

    def test_severe_imbalance_triggers_review_action(self):
        tests = self._all_unit_tests(10)
        event = ConfidenceMagnet().observe("m1", "test_results", {"tests": tests, "recommended_action": "none"})
        assert event.recommended_action == "review"

    def test_severe_imbalance_adds_warnings_to_evidence(self):
        tests = self._all_unit_tests(10)
        event = ConfidenceMagnet().observe("m1", "test_results", {"tests": tests})
        assert len(event.evidence) > 0

    def test_moderate_imbalance_reduces_confidence_slightly(self):
        # Moderate imbalance: 85% unit, 15% integration, 0% e2e
        tests = [{"layer": "unit"} for _ in range(85)]
        tests += [{"layer": "integration"} for _ in range(15)]
        event = ConfidenceMagnet().observe("m1", "test_results", {"tests": tests})
        # max_deviation >= 0.15 reduces confidence by 0.03
        assert event.confidence_delta <= -0.03

    def test_balanced_pyramid_no_extra_adjustments(self):
        """A perfectly balanced pyramid produces zero pyramid-driven deltas."""
        tests = self._balanced_tests()
        event = ConfidenceMagnet().observe("m1", "test_results", {"tests": tests})
        # With balanced pyramid, no warnings, so no adjustments beyond signal passthrough
        assert event.risk_delta == 0.0

    def test_no_tests_signal_not_analyzed(self):
        """Without a tests key, no pyramid analysis is done."""
        event = ConfidenceMagnet().observe("m1", "test_results", {})
        assert "test_pyramid" not in event.observed_signal

    def test_uses_test_results_key_alias(self):
        """Pyramid should also be triggered via 'test_results' key (not just 'tests')."""
        tests = self._all_unit_tests(10)
        event = ConfidenceMagnet().observe("m1", "test_results", {"test_results": tests})
        assert "test_pyramid" in event.observed_signal
