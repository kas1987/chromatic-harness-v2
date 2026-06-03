"""Tests for magnets.plugins.pyramid_plugin — PyramidCheckPlugin."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import MagnetEvent
from magnets.plugin import MagnetPlugin
from magnets.plugins.pyramid_plugin import PyramidCheckPlugin

_PYRAMID_POINTS = ["test_results", "tests_complete", "validation"]


class TestPyramidCheckPluginInterface:
    def test_is_magnet_plugin(self):
        assert isinstance(PyramidCheckPlugin(), MagnetPlugin)

    def test_name(self):
        assert PyramidCheckPlugin.name == "pyramid_check_plugin"

    def test_observe_returns_magnet_event(self):
        event = PyramidCheckPlugin().observe("m1", "intake", {})
        assert isinstance(event, MagnetEvent)


class TestPyramidCheckPluginNonPyramidPoint:
    def test_non_pyramid_point_zero_deltas(self):
        event = PyramidCheckPlugin().observe("m1", "intake", {"tests": [{"layer": "unit"}]})
        assert event.risk_delta == 0.0
        assert event.confidence_delta == 0.0

    def test_non_pyramid_point_no_pyramid_in_signal(self):
        event = PyramidCheckPlugin().observe("m1", "intake", {"tests": [{"layer": "unit"}]})
        assert "test_pyramid" not in event.observed_signal

    def test_non_pyramid_point_default_action(self):
        event = PyramidCheckPlugin().observe("m1", "dispatch", {})
        assert event.recommended_action == "none"


class TestPyramidCheckPluginActivation:
    def _balanced_tests(self):
        return [{"layer": "unit"}] * 7 + [{"layer": "integration"}] * 2 + [{"layer": "e2e"}] * 1

    def test_pyramid_analysis_at_test_results(self):
        event = PyramidCheckPlugin().observe("m1", "test_results", {"tests": self._balanced_tests()})
        assert "test_pyramid" in event.observed_signal

    def test_pyramid_analysis_at_tests_complete(self):
        event = PyramidCheckPlugin().observe("m1", "tests_complete", {"tests": self._balanced_tests()})
        assert "test_pyramid" in event.observed_signal

    def test_pyramid_analysis_at_validation(self):
        event = PyramidCheckPlugin().observe("m1", "validation", {"tests": self._balanced_tests()})
        assert "test_pyramid" in event.observed_signal

    def test_uses_test_results_alias(self):
        tests = self._balanced_tests()
        event = PyramidCheckPlugin().observe("m1", "test_results", {"test_results": tests})
        assert "test_pyramid" in event.observed_signal


class TestPyramidCheckPluginSevereImbalance:
    def _all_unit(self, n=10):
        return [{"layer": "unit"}] * n

    def test_severe_imbalance_raises_risk(self):
        event = PyramidCheckPlugin().observe("m1", "test_results", {"tests": self._all_unit()})
        assert event.risk_delta == 0.05

    def test_severe_imbalance_confidence_negative(self):
        event = PyramidCheckPlugin().observe("m1", "test_results", {"tests": self._all_unit()})
        assert event.confidence_delta == -0.08

    def test_severe_imbalance_review_action(self):
        event = PyramidCheckPlugin().observe("m1", "test_results", {"tests": self._all_unit()})
        assert event.recommended_action == "review"

    def test_severe_imbalance_adds_warnings_evidence(self):
        event = PyramidCheckPlugin().observe("m1", "test_results", {"tests": self._all_unit()})
        assert len(event.evidence) > 0


class TestPyramidCheckPluginModerateImbalance:
    def _moderate_tests(self):
        # 85% unit, 15% integration, 0% e2e — moderate deviation
        return [{"layer": "unit"}] * 85 + [{"layer": "integration"}] * 15

    def test_moderate_imbalance_slight_confidence_reduction(self):
        event = PyramidCheckPlugin().observe("m1", "test_results", {"tests": self._moderate_tests()})
        assert event.confidence_delta == -0.03

    def test_moderate_imbalance_no_risk_delta(self):
        event = PyramidCheckPlugin().observe("m1", "test_results", {"tests": self._moderate_tests()})
        assert event.risk_delta == 0.0


class TestPyramidCheckPluginBalanced:
    def _balanced(self):
        return [{"layer": "unit"}] * 7 + [{"layer": "integration"}] * 2 + [{"layer": "e2e"}] * 1

    def test_balanced_no_risk(self):
        event = PyramidCheckPlugin().observe("m1", "test_results", {"tests": self._balanced()})
        assert event.risk_delta == 0.0

    def test_balanced_no_confidence_reduction(self):
        event = PyramidCheckPlugin().observe("m1", "test_results", {"tests": self._balanced()})
        assert event.confidence_delta == 0.0

    def test_balanced_default_action(self):
        event = PyramidCheckPlugin().observe("m1", "test_results", {"tests": self._balanced()})
        assert event.recommended_action == "none"
