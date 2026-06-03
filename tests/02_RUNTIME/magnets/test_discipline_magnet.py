"""Tests for magnets.discipline_magnet — DisciplineMagnet."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.discipline_magnet import DisciplineMagnet


class TestDisciplineMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(DisciplineMagnet, BaseMagnet)

    def test_name(self):
        assert DisciplineMagnet.name == "discipline_magnet"

    def test_observe_returns_magnet_event(self):
        event = DisciplineMagnet().observe("m1", "discipline_check", {})
        assert isinstance(event, MagnetEvent)


class TestDisciplineMagnetWriteWithoutRead:
    """WRITE without READ is a Karpathy discipline violation."""

    def test_write_without_read_raises_risk(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "read_paths": [],
                "modified_paths": ["src/app.py"],
            },
        )
        assert event.risk_delta > 0

    def test_write_without_read_evidence(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "read_paths": [],
                "modified_paths": ["src/app.py"],
            },
        )
        assert any("WRITE without READ" in e for e in event.evidence)

    def test_write_after_read_no_read_evidence(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "read_paths": ["src/app.py"],
                "modified_paths": ["src/app.py"],
            },
        )
        assert not any("WRITE without READ" in e for e in event.evidence)

    def test_multiple_writes_without_read_each_penalized(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "read_paths": [],
                "modified_paths": ["a.py", "b.py"],
            },
        )
        # 2 violations * 0.2 = 0.4
        assert event.risk_delta >= 0.4


class TestDisciplineMagnetSuccessCriteria:
    def test_no_success_criteria_raises_risk(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {"has_success_criteria": False},
        )
        assert event.risk_delta > 0

    def test_missing_success_criteria_evidence(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {"has_success_criteria": False},
        )
        assert any("success criteria" in e for e in event.evidence)

    def test_success_criteria_present_no_evidence(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "has_success_criteria": True,
                "read_paths": ["a.py"],
                "modified_paths": ["a.py"],
                "verification_ran": True,
            },
        )
        assert not any("success criteria" in e for e in event.evidence)


class TestDisciplineMagnetAssumptions:
    def test_assumptions_not_stated_at_pre_implementation_raises_risk(self):
        event = DisciplineMagnet().observe(
            "m1", "pre_implementation",
            {"assumptions_stated": False},
        )
        assert event.risk_delta > 0
        assert any("Assumptions" in e for e in event.evidence)

    def test_assumptions_not_stated_at_other_point_no_risk(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {"assumptions_stated": False, "has_success_criteria": True},
        )
        assert not any("Assumptions" in e for e in event.evidence)

    def test_assumptions_at_discipline_check_raises_risk(self):
        event = DisciplineMagnet().observe(
            "m1", "discipline_check",
            {"assumptions_stated": False},
        )
        assert any("Assumptions" in e for e in event.evidence)


class TestDisciplineMagnetVerification:
    def test_modified_without_verification_at_post_implementation(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "read_paths": ["a.py"],
                "modified_paths": ["a.py"],
                "has_success_criteria": True,
                "verification_ran": False,
            },
        )
        assert any("not verified" in e for e in event.evidence)

    def test_verified_no_verification_evidence(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "read_paths": ["a.py"],
                "modified_paths": ["a.py"],
                "has_success_criteria": True,
                "verification_ran": True,
            },
        )
        assert not any("not verified" in e for e in event.evidence)


class TestDisciplineMagnetScopeCreep:
    def test_unexpected_modification_raises_risk(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "read_paths": ["a.py", "b.py"],
                "modified_paths": ["a.py", "b.py"],
                "expected_paths": ["a.py"],
                "has_success_criteria": True,
                "verification_ran": True,
            },
        )
        assert any("UNEXPECTED change" in e for e in event.evidence)

    def test_scope_creep_many_files(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "read_paths": [f"f{i}.py" for i in range(5)],
                "modified_paths": [f"f{i}.py" for i in range(5)],
                "expected_paths": ["f0.py"],
                "has_success_criteria": True,
                "verification_ran": True,
            },
        )
        assert any("SCOPE CREEP" in e for e in event.evidence)

    def test_within_expected_paths_no_scope_creep(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "read_paths": ["a.py"],
                "modified_paths": ["a.py"],
                "expected_paths": ["a.py"],
                "has_success_criteria": True,
                "verification_ran": True,
            },
        )
        assert not any("SCOPE CREEP" in e for e in event.evidence)


class TestDisciplineMagnetOversizedDiff:
    def test_oversized_diff_raises_risk(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "lines_changed": 500,
                "max_lines_hint": 100,
                "has_success_criteria": True,
            },
        )
        assert any("OVERSIZED diff" in e for e in event.evidence)

    def test_within_hint_no_oversized_evidence(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {
                "lines_changed": 50,
                "max_lines_hint": 100,
                "has_success_criteria": True,
            },
        )
        assert not any("OVERSIZED diff" in e for e in event.evidence)

    def test_no_hint_no_oversized_check(self):
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {"lines_changed": 9999, "has_success_criteria": True},
        )
        assert not any("OVERSIZED diff" in e for e in event.evidence)


class TestDisciplineMagnetCleanExecution:
    def _clean_signal(self):
        return {
            "read_paths": ["src/a.py"],
            "modified_paths": ["src/a.py"],
            "expected_paths": ["src/a.py"],
            "has_success_criteria": True,
            "assumptions_stated": True,
            "verification_ran": True,
        }

    def test_clean_execution_positive_confidence(self):
        event = DisciplineMagnet().observe("m1", "post_implementation", self._clean_signal())
        assert event.confidence_delta > 0

    def test_clean_execution_proceed_action(self):
        event = DisciplineMagnet().observe("m1", "post_implementation", self._clean_signal())
        assert event.recommended_action == "proceed"

    def test_clean_execution_evidence_contains_karpathy(self):
        event = DisciplineMagnet().observe("m1", "post_implementation", self._clean_signal())
        assert any("Karpathy discipline" in e for e in event.evidence)

    def test_clean_execution_zero_risk(self):
        event = DisciplineMagnet().observe("m1", "post_implementation", self._clean_signal())
        assert event.risk_delta == 0.0


class TestDisciplineMagnetRecommendations:
    def test_high_risk_halt_and_review(self):
        # write without read on many files -> risk >= 0.3
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {"modified_paths": ["a.py", "b.py", "c.py"], "read_paths": []},
        )
        assert event.recommended_action == "halt_and_review"

    def test_medium_risk_narrow_scope(self):
        # One write-without-read + no success criteria -> between 0.15 and 0.3
        event = DisciplineMagnet().observe(
            "m1", "post_implementation",
            {"modified_paths": ["a.py"], "read_paths": [], "has_success_criteria": False},
        )
        assert event.recommended_action in ("narrow_scope", "halt_and_review")
