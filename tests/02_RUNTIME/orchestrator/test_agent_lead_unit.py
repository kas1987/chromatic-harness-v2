"""Tests for orchestrator/agent_lead.py — AgentLead decision synthesis pipeline.

# DEFICIENCIES NOTED
# 1. agent_lead.py hard-wires a _load_local() call for session_compact inside run(),
#    making it impossible to fully unit-test run() without either patching _load_local
#    at module level or accepting that the try/except silences the failure. Tests here
#    mock _load_local in run() via patch.object on the module.
#
# 2. decision_from_score is also loaded via _load_local at module import time (not at
#    test time), so it is already bound when tests run. The confidence_engine module is
#    loaded once at module-load and not easily re-mockable per test. Tests work around
#    this by constructing MagnetReport.score values that drive known decision_from_score
#    outcomes (>=90 → proceed, 75-89 → proceed_reversible_only, 50-74 → replan,
#    <50 → halt).
#
# 3. _suggest_bead uses report.feedback[:3] — if feedback is empty, the bead objective
#    contains "Findings: " with no content. This is a minor cosmetic deficiency.
#
# 4. MagnetOrchestrator.default_registry() pulls in scope_magnet which requires
#    aiosqlite at import time. Any test that constructs AgentLead() without supplying
#    an orchestrator will fail in the test environment unless aiosqlite is installed.
#    All tests here inject a mock orchestrator to avoid this.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# ---------------------------------------------------------------------------
# Module loaders — keep agent_lead isolated from session_compact at import time
# ---------------------------------------------------------------------------

_AL_PATH = _RUNTIME / "orchestrator" / "agent_lead.py"


def _load_agent_lead_module(name: str = "agent_lead_under_test"):
    """Load agent_lead.py fresh into a private sys.modules key."""
    spec = importlib.util.spec_from_file_location(name, _AL_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load once for the module — re-used across all test classes via fixtures.
_AL_MOD = _load_agent_lead_module("agent_lead_tests_main")

AgentLead = _AL_MOD.AgentLead
AgentLeadOutput = _AL_MOD.AgentLeadOutput

# ---------------------------------------------------------------------------
# MagnetReport / NormalizedEvent imports (real, lightweight)
# ---------------------------------------------------------------------------

from magnets.magnet_orchestrator import MagnetReport, NormalizedEvent  # noqa: E402
from magnets.base_magnet import MagnetEvent  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers / builders
# ---------------------------------------------------------------------------


def _make_report(
    *,
    mission_id: str = "CHR-TEST",
    collected_count: int = 2,
    normalized: list[NormalizedEvent] | None = None,
    correlated: dict[str, Any] | None = None,
    score: float = 85.0,
    confidence_score: float = 85.0,
    risk_score: float = 0.0,
    feedback: list[str] | None = None,
    recommendation: str = "proceed_reversible_only",
    gold_artifact: dict[str, Any] | None = None,
) -> MagnetReport:
    """Construct a MagnetReport with sensible defaults."""
    return MagnetReport(
        mission_id=mission_id,
        collected_count=collected_count,
        normalized=normalized or [],
        correlated=correlated
        or {
            "magnets_seen": ["confidence_magnet"],
            "total_risk_delta": 0.0,
            "total_confidence_delta": 10.0,
            "escalations": 0,
        },
        score=score,
        confidence_score=confidence_score,
        risk_score=risk_score,
        feedback=feedback or ["High-confidence mission; safe to auto-proceed."],
        recommendation=recommendation,
        gold_artifact=gold_artifact or {},
    )


def _make_mission(
    *,
    mission_id: str = "CHR-TEST",
    objective: str = "Test objective",
    confidence_required: float = 75.0,
    autonomy_level: str = "L2",
) -> dict[str, Any]:
    return {
        "mission_id": mission_id,
        "objective": objective,
        "confidence_required": confidence_required,
        "autonomy_level": autonomy_level,
    }


def _make_normalized_event(
    *,
    mission_id: str = "CHR-TEST",
    magnet_name: str = "confidence_magnet",
    inflection_point: str = "validation",
    risk_delta: float = 0.0,
    confidence_delta: float = 5.0,
    recommended_action: str = "proceed",
    evidence: list[str] | None = None,
    signal_keys: list[str] | None = None,
) -> NormalizedEvent:
    return NormalizedEvent(
        mission_id=mission_id,
        magnet_name=magnet_name,
        inflection_point=inflection_point,
        risk_delta=risk_delta,
        confidence_delta=confidence_delta,
        recommended_action=recommended_action,
        evidence=evidence or [],
        signal_keys=signal_keys or [],
    )


def _run_with_mock_sc(agent_lead: AgentLead, mission: dict[str, Any], events: list) -> AgentLeadOutput:
    """Run AgentLead.run() with session_compact stubbed out."""
    mock_sc = MagicMock()
    mock_sc.write_handoff = MagicMock()
    # _load_local is called twice: once at module-import (confidence_engine) and
    # once inside run() (session_compact). We only need to stub the run()-time call.
    original = _AL_MOD._load_local

    def _patched_load(name, filename):
        if filename == "session_compact.py":
            return mock_sc
        return original(name, filename)

    with patch.object(_AL_MOD, "_load_local", side_effect=_patched_load):
        return agent_lead.run(mission, events)


# ---------------------------------------------------------------------------
# TestAgentLeadOutput — dataclass contract
# ---------------------------------------------------------------------------


class TestAgentLeadOutput:
    """Verify the AgentLeadOutput dataclass stores all fields correctly."""

    def test_fields_stored(self):
        out = AgentLeadOutput(
            final_report={"k": "v"},
            pr_package={"title": "PR"},
            next_steps={"actions": []},
            audit_log={"mission_id": "m"},
            handoff_prep={"directive_summary": "x"},
            suggested_bead={"title": "bead"},
            decision="proceed",
            composite_score=92.5,
        )
        assert out.final_report == {"k": "v"}
        assert out.pr_package == {"title": "PR"}
        assert out.next_steps == {"actions": []}
        assert out.audit_log == {"mission_id": "m"}
        assert out.handoff_prep == {"directive_summary": "x"}
        assert out.suggested_bead == {"title": "bead"}
        assert out.decision == "proceed"
        assert out.composite_score == 92.5

    def test_default_decision_is_review(self):
        out = AgentLeadOutput(
            final_report={},
            pr_package={},
            next_steps={},
            audit_log={},
            handoff_prep={},
        )
        assert out.decision == "review"

    def test_default_composite_score_is_zero(self):
        out = AgentLeadOutput(
            final_report={},
            pr_package={},
            next_steps={},
            audit_log={},
            handoff_prep={},
        )
        assert out.composite_score == 0.0

    def test_default_suggested_bead_is_none(self):
        out = AgentLeadOutput(
            final_report={},
            pr_package={},
            next_steps={},
            audit_log={},
            handoff_prep={},
        )
        assert out.suggested_bead is None


# ---------------------------------------------------------------------------
# TestAgentLeadRunOutputDocuments — all five output sections populated
# ---------------------------------------------------------------------------


class TestAgentLeadRunOutputDocuments:
    """run() must produce all six output documents regardless of scenario."""

    def _lead(self, report: MagnetReport) -> AgentLead:
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        return AgentLead(orchestrator=mock_orch)

    def test_all_output_sections_present(self):
        report = _make_report()
        mission = _make_mission()
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert out.final_report is not None
        assert out.pr_package is not None
        assert out.next_steps is not None
        assert out.audit_log is not None
        assert out.handoff_prep is not None

    def test_final_report_has_required_keys(self):
        report = _make_report()
        mission = _make_mission(mission_id="CHR-DOCS-1")
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        fr = out.final_report
        assert "executive_summary" in fr
        assert "objective" in fr
        assert "synthesis" in fr
        assert "evaluation" in fr
        assert "recommendation" in fr
        assert "achievements" in fr
        assert "findings" in fr

    def test_executive_summary_contains_mission_id(self):
        report = _make_report(mission_id="CHR-SUMMARY")
        mission = _make_mission(mission_id="CHR-SUMMARY")
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert "CHR-SUMMARY" in out.final_report["executive_summary"]

    def test_executive_summary_contains_score(self):
        report = _make_report(score=87.5)
        mission = _make_mission()
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert "87.5" in out.final_report["executive_summary"]

    def test_executive_summary_contains_decision(self):
        report = _make_report(score=95.0, recommendation="proceed")
        mission = _make_mission()
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert out.decision in out.final_report["executive_summary"]

    def test_composite_score_equals_report_score(self):
        report = _make_report(score=78.25)
        mission = _make_mission()
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert out.composite_score == 78.25

    def test_audit_log_mission_id(self):
        report = _make_report(mission_id="CHR-AUDIT")
        mission = _make_mission(mission_id="CHR-AUDIT")
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert out.audit_log["mission_id"] == "CHR-AUDIT"

    def test_audit_log_event_count(self):
        report = _make_report()
        events = [
            MagnetEvent("CHR-TEST", "confidence_magnet", "validation", {}),
            MagnetEvent("CHR-TEST", "security_magnet", "execution", {}),
        ]
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        out = _run_with_mock_sc(lead, _make_mission(), events)

        assert out.audit_log["event_count"] == 2

    def test_audit_log_gold_artifact_ref(self):
        report = _make_report(mission_id="CHR-GOLD", gold_artifact={"ref": "artifact-1"})
        mission = _make_mission(mission_id="CHR-GOLD")
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        out = _run_with_mock_sc(lead, mission, [])

        assert out.audit_log["gold_artifact_ref"] == {"ref": "artifact-1"}

    def test_handoff_prep_directive_summary(self):
        report = _make_report()
        mission = _make_mission()
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert out.handoff_prep["directive_summary"]

    def test_handoff_prep_context_snapshot_contains_mission_id(self):
        report = _make_report(mission_id="CHR-SNAP")
        mission = _make_mission(mission_id="CHR-SNAP")
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        snap = out.handoff_prep["context_snapshot"]
        assert snap["mission_id"] == "CHR-SNAP"

    def test_handoff_prep_context_snapshot_autonomy_level(self):
        report = _make_report()
        mission = _make_mission(autonomy_level="L3")
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert out.handoff_prep["context_snapshot"]["autonomy_level"] == "L3"

    def test_handoff_prep_context_snapshot_composite_score(self):
        report = _make_report(score=91.0)
        mission = _make_mission()
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert out.handoff_prep["context_snapshot"]["composite_score"] == 91.0

    def test_pr_package_title_contains_objective(self):
        report = _make_report()
        mission = _make_mission(objective="Implement OAuth login flow")
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert "Implement OAuth login flow" in out.pr_package["title"]

    def test_pr_package_checklist_has_two_items(self):
        report = _make_report()
        mission = _make_mission()
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        assert len(out.pr_package["checklist"]) == 2

    def test_achievements_mention_event_count(self):
        report = _make_report(collected_count=7)
        mission = _make_mission()
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        ach = " ".join(out.final_report["achievements"])
        assert "7" in ach

    def test_achievements_mention_confidence(self):
        report = _make_report(confidence_score=88.5)
        mission = _make_mission()
        lead = self._lead(report)
        out = _run_with_mock_sc(lead, mission, [])

        ach = " ".join(out.final_report["achievements"])
        assert "88.5" in ach


# ---------------------------------------------------------------------------
# TestDecisionPipeline — the core branching logic of _recommend()
# ---------------------------------------------------------------------------


class TestDecisionPipeline:
    """Verify all decision outcomes and their priority for the run() pipeline."""

    def _run(self, report: MagnetReport, mission: dict | None = None) -> AgentLeadOutput:
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        return _run_with_mock_sc(lead, mission or _make_mission(), [])

    def test_score_ge_90_produces_proceed(self):
        report = _make_report(score=92.0, recommendation="proceed")
        out = self._run(report)
        assert out.decision == "proceed"

    def test_score_between_75_and_90_produces_proceed_reversible_only(self):
        report = _make_report(
            score=80.0,
            confidence_score=80.0,
            recommendation="proceed_reversible_only",
        )
        out = self._run(report, _make_mission(confidence_required=75.0))
        assert out.decision == "proceed_reversible_only"

    def test_score_between_50_and_75_produces_replan(self):
        report = _make_report(
            score=62.0,
            confidence_score=70.0,
            recommendation="replan",
        )
        out = self._run(report, _make_mission(confidence_required=75.0))
        # confidence_score (70) < required (75) → alignment fails → replan
        assert out.decision == "replan"

    def test_report_recommendation_halt_overrides_score(self):
        """Even a high score must yield 'halt' when report.recommendation == 'halt'."""
        report = _make_report(score=95.0, recommendation="halt")
        out = self._run(report)
        assert out.decision == "halt"

    def test_alignment_failure_overrides_score_to_replan(self):
        """confidence_score below required → replan, regardless of quality score."""
        report = _make_report(
            score=82.0,
            confidence_score=70.0,  # below required 80
            recommendation="proceed_reversible_only",
        )
        out = self._run(report, _make_mission(confidence_required=80.0))
        assert out.decision == "replan"

    def test_halt_takes_priority_over_alignment_failure(self):
        """report.recommendation == 'halt' beats the alignment check."""
        report = _make_report(
            score=60.0,
            confidence_score=60.0,  # below required 90
            recommendation="halt",
        )
        out = self._run(report, _make_mission(confidence_required=90.0))
        assert out.decision == "halt"

    def test_alignment_met_preserves_score_based_decision(self):
        """When confidence_score >= required, decision comes from score band."""
        report = _make_report(
            score=82.0,
            confidence_score=85.0,  # above required 80
            recommendation="proceed_reversible_only",
        )
        out = self._run(report, _make_mission(confidence_required=80.0))
        assert out.decision == "proceed_reversible_only"

    @pytest.mark.parametrize(
        "score,expected",
        [
            (90.0, "proceed"),
            (95.0, "proceed"),
            (75.0, "proceed_reversible_only"),
            (89.9, "proceed_reversible_only"),
            (50.0, "replan"),
            (74.9, "replan"),
            (49.9, "halt"),
            (0.0, "halt"),
        ],
    )
    def test_decision_from_score_band(self, score, expected):
        """Score bands map to correct decisions when alignment is met."""
        report = _make_report(
            score=score,
            confidence_score=score,  # alignment always met: required=0
            recommendation={
                "proceed": "proceed",
                "proceed_reversible_only": "proceed_reversible_only",
                "replan": "replan",
                "halt": "halt",
            }.get(expected, expected),
        )
        out = self._run(report, _make_mission(confidence_required=0.0))
        assert out.decision == expected


# ---------------------------------------------------------------------------
# TestSynthesisStage — _synthesize() sub-stage
# ---------------------------------------------------------------------------


class TestSynthesisStage:
    """Verify the synthesis section of the final report."""

    def _run(self, report: MagnetReport, mission: dict) -> AgentLeadOutput:
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        return _run_with_mock_sc(lead, mission, [])

    def test_synthesis_mission_id(self):
        report = _make_report(mission_id="CHR-SYN-1")
        mission = _make_mission(mission_id="CHR-SYN-1")
        out = self._run(report, mission)
        assert out.final_report["synthesis"]["mission_id"] == "CHR-SYN-1"

    def test_synthesis_objective(self):
        report = _make_report()
        mission = _make_mission(objective="Refactor authentication module")
        out = self._run(report, mission)
        assert out.final_report["synthesis"]["objective"] == "Refactor authentication module"

    def test_synthesis_event_count(self):
        report = _make_report(collected_count=11)
        out = self._run(report, _make_mission())
        assert out.final_report["synthesis"]["event_count"] == 11

    def test_synthesis_magnets_seen(self):
        corr = {
            "magnets_seen": ["scope_magnet", "security_magnet"],
            "total_risk_delta": 0.0,
            "total_confidence_delta": 5.0,
            "escalations": 0,
        }
        report = _make_report(correlated=corr)
        out = self._run(report, _make_mission())
        assert "scope_magnet" in out.final_report["synthesis"]["magnets_seen"]
        assert "security_magnet" in out.final_report["synthesis"]["magnets_seen"]

    def test_synthesis_key_findings(self):
        report = _make_report(feedback=["Finding A", "Finding B"])
        out = self._run(report, _make_mission())
        assert out.final_report["synthesis"]["key_findings"] == ["Finding A", "Finding B"]

    def test_synthesis_risk_summary_from_correlated(self):
        corr = {
            "magnets_seen": [],
            "total_risk_delta": 0.42,
            "total_confidence_delta": 0.0,
            "escalations": 0,
        }
        report = _make_report(correlated=corr)
        out = self._run(report, _make_mission())
        assert out.final_report["synthesis"]["risk_summary"] == 0.42

    def test_synthesis_confidence_summary_from_correlated(self):
        corr = {
            "magnets_seen": [],
            "total_risk_delta": 0.0,
            "total_confidence_delta": 12.5,
            "escalations": 0,
        }
        report = _make_report(correlated=corr)
        out = self._run(report, _make_mission())
        assert out.final_report["synthesis"]["confidence_summary"] == 12.5


# ---------------------------------------------------------------------------
# TestEvaluationStage — _evaluate() sub-stage
# ---------------------------------------------------------------------------


class TestEvaluationStage:
    """Verify the evaluation section correctness."""

    def _run(self, report: MagnetReport, mission: dict) -> AgentLeadOutput:
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        return _run_with_mock_sc(lead, mission, [])

    def test_evaluation_quality_score(self):
        report = _make_report(score=77.3)
        out = self._run(report, _make_mission())
        assert out.final_report["evaluation"]["quality_score"] == 77.3

    def test_evaluation_confidence_score(self):
        report = _make_report(confidence_score=82.0)
        out = self._run(report, _make_mission())
        assert out.final_report["evaluation"]["confidence_score"] == 82.0

    def test_evaluation_risk_score(self):
        report = _make_report(risk_score=0.35)
        out = self._run(report, _make_mission())
        assert out.final_report["evaluation"]["risk_score"] == 0.35

    def test_alignment_true_when_confidence_meets_required(self):
        report = _make_report(confidence_score=80.0)
        out = self._run(report, _make_mission(confidence_required=75.0))
        assert out.final_report["evaluation"]["alignment_with_required"] is True

    def test_alignment_true_when_confidence_exactly_equals_required(self):
        report = _make_report(confidence_score=75.0)
        out = self._run(report, _make_mission(confidence_required=75.0))
        assert out.final_report["evaluation"]["alignment_with_required"] is True

    def test_alignment_false_when_confidence_below_required(self):
        report = _make_report(confidence_score=70.0)
        out = self._run(report, _make_mission(confidence_required=80.0))
        assert out.final_report["evaluation"]["alignment_with_required"] is False

    def test_required_confidence_echoed(self):
        report = _make_report(confidence_score=80.0)
        out = self._run(report, _make_mission(confidence_required=88.5))
        assert out.final_report["evaluation"]["required_confidence"] == 88.5

    def test_validation_events_count_validation_magnet(self):
        ne = _make_normalized_event(magnet_name="validation_magnet", inflection_point="plan")
        report = _make_report(normalized=[ne])
        out = self._run(report, _make_mission())
        assert out.final_report["evaluation"]["validation_events"] == 1

    def test_validation_events_count_inflection_point_validation(self):
        ne = _make_normalized_event(magnet_name="confidence_magnet", inflection_point="validation")
        report = _make_report(normalized=[ne])
        out = self._run(report, _make_mission())
        assert out.final_report["evaluation"]["validation_events"] == 1

    def test_validation_events_count_both_conditions(self):
        ne1 = _make_normalized_event(magnet_name="validation_magnet", inflection_point="plan")
        ne2 = _make_normalized_event(magnet_name="scope_magnet", inflection_point="validation")
        ne3 = _make_normalized_event(magnet_name="scope_magnet", inflection_point="execution")
        report = _make_report(normalized=[ne1, ne2, ne3])
        out = self._run(report, _make_mission())
        assert out.final_report["evaluation"]["validation_events"] == 2

    def test_tests_passing_signal_true_when_no_fail_in_evidence(self):
        ne = _make_normalized_event(
            magnet_name="validation_magnet",
            inflection_point="validation",
            evidence=["all_tests_pass", "coverage_ok"],
        )
        report = _make_report(normalized=[ne])
        out = self._run(report, _make_mission())
        assert out.final_report["evaluation"]["tests_passing_signal"] is True

    def test_tests_passing_signal_false_when_fail_in_evidence(self):
        ne = _make_normalized_event(
            magnet_name="validation_magnet",
            inflection_point="validation",
            evidence=["test_suite_fail", "coverage_low"],
        )
        report = _make_report(normalized=[ne])
        out = self._run(report, _make_mission())
        assert out.final_report["evaluation"]["tests_passing_signal"] is False

    def test_tests_passing_signal_false_case_insensitive(self):
        ne = _make_normalized_event(
            magnet_name="validation_magnet",
            inflection_point="validation",
            evidence=["FAIL_DETECTED"],
        )
        report = _make_report(normalized=[ne])
        out = self._run(report, _make_mission())
        assert out.final_report["evaluation"]["tests_passing_signal"] is False

    def test_tests_passing_signal_true_when_no_validation_events(self):
        ne = _make_normalized_event(
            magnet_name="scope_magnet",
            inflection_point="execution",
            evidence=["fail_here"],  # Evidence with 'fail' but not validation event
        )
        report = _make_report(normalized=[ne])
        out = self._run(report, _make_mission())
        # No validation_magnet events → no fail evidence checked → True
        assert out.final_report["evaluation"]["tests_passing_signal"] is True


# ---------------------------------------------------------------------------
# TestNextStepsStage — _next_steps() decision-specific actions
# ---------------------------------------------------------------------------


class TestNextStepsStage:
    """Verify the next_steps output for each decision type."""

    def _run(self, report: MagnetReport, mission: dict) -> AgentLeadOutput:
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        return _run_with_mock_sc(lead, mission, [])

    @pytest.mark.parametrize(
        "score,recommendation,expected_action_fragment",
        [
            (92.0, "proceed", "Auto-proceed"),
            (80.0, "proceed_reversible_only", "reversible"),
            (62.0, "replan", "Replan"),
            (30.0, "halt", "Halt"),
        ],
    )
    def test_next_steps_action_by_decision(self, score, recommendation, expected_action_fragment):
        report = _make_report(
            score=score,
            confidence_score=score,
            recommendation=recommendation,
        )
        out = self._run(report, _make_mission(confidence_required=0.0))
        actions = " ".join(out.next_steps["actions"])
        assert expected_action_fragment in actions

    def test_halt_priority_is_p0(self):
        report = _make_report(score=30.0, recommendation="halt")
        out = self._run(report, _make_mission())
        assert out.next_steps["priority"] == "p0"

    def test_non_halt_priority_is_p2(self):
        report = _make_report(score=85.0, recommendation="proceed_reversible_only")
        out = self._run(report, _make_mission())
        assert out.next_steps["priority"] == "p2"

    def test_escalation_adds_action(self):
        corr = {
            "magnets_seen": [],
            "total_risk_delta": 0.0,
            "total_confidence_delta": 10.0,
            "escalations": 2,
        }
        report = _make_report(score=92.0, recommendation="proceed", correlated=corr)
        out = self._run(report, _make_mission())
        combined = " ".join(out.next_steps["actions"])
        assert "escalated" in combined.lower()

    def test_no_escalation_no_extra_action(self):
        corr = {
            "magnets_seen": [],
            "total_risk_delta": 0.0,
            "total_confidence_delta": 10.0,
            "escalations": 0,
        }
        report = _make_report(score=92.0, recommendation="proceed", correlated=corr)
        out = self._run(report, _make_mission())
        assert len(out.next_steps["actions"]) == 1

    def test_next_steps_objective_echoed(self):
        report = _make_report()
        mission = _make_mission(objective="Deploy microservices")
        out = self._run(report, mission)
        assert out.next_steps["objective"] == "Deploy microservices"

    def test_next_steps_review_decision_falls_through(self):
        """_next_steps() 'else' branch maps to 'Create review package' action.

        The 'review' decision is not reachable from _recommend() via the normal
        scoring path (decision_from_score() only emits 'review' when
        human_gate_required=True, which _recommend() never passes).  We test
        the _next_steps() method directly to verify the else-branch.
        """
        mock_orch = MagicMock()
        mock_orch.process.return_value = _make_report()
        lead = AgentLead(orchestrator=mock_orch)
        report = _make_report()
        # Call _next_steps directly with an artificial "review" recommendation
        recommendation = {"decision": "review", "magnet_recommendation": "review", "rationale": []}
        ns = lead._next_steps(_make_mission(), recommendation, report)
        actions = " ".join(ns["actions"])
        assert "review" in actions.lower()


# ---------------------------------------------------------------------------
# TestPrPackageStage — _pr_package() logic
# ---------------------------------------------------------------------------


class TestPrPackageStage:
    """Verify PR package construction."""

    def _run(self, report: MagnetReport, mission: dict) -> AgentLeadOutput:
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        return _run_with_mock_sc(lead, mission, [])

    @pytest.mark.parametrize(
        "decision,expected_ready",
        [
            ("proceed", True),
            ("proceed_reversible_only", True),
            ("replan", False),
            ("halt", False),
        ],
    )
    def test_ready_for_review_by_decision(self, decision, expected_ready):
        # Map decision to a score that produces it organically.
        # Note: 'review' is not a reachable output from _recommend() because
        # decision_from_score() only returns 'review' when human_gate_required=True,
        # which _recommend() never passes. 'review' is therefore excluded from this
        # parametrized set; its pr_package behaviour is tested separately below.
        score_map = {
            "proceed": 92.0,
            "proceed_reversible_only": 80.0,
            "replan": 62.0,
            "halt": 30.0,
        }
        score = score_map[decision]
        report = _make_report(
            score=score,
            confidence_score=score,
            recommendation=decision,
        )
        out = self._run(report, _make_mission(confidence_required=0.0))
        assert out.pr_package["ready_for_review"] == expected_ready

    def test_pr_package_review_decision_not_ready_for_review(self):
        """When _pr_package is called directly with a 'review' decision, ready_for_review=False."""
        mock_orch = MagicMock()
        mock_orch.process.return_value = _make_report()
        lead = AgentLead(orchestrator=mock_orch)
        evaluation = {"quality_score": 75.0, "alignment_with_required": True, "tests_passing_signal": True}
        recommendation = {"decision": "review"}
        pkg = lead._pr_package(_make_mission(), evaluation, recommendation)
        assert pkg["ready_for_review"] is False

    def test_pr_title_truncates_at_80_chars(self):
        long_objective = "A" * 100
        mission = _make_mission(objective=long_objective)
        report = _make_report()
        out = self._run(report, mission)
        # Title is "[Agent Lead] " (13 chars) + 80 chars of objective
        assert len(out.pr_package["title"]) <= 13 + 80

    def test_pr_checklist_confidence_alignment_item(self):
        report = _make_report(confidence_score=85.0)
        out = self._run(report, _make_mission(confidence_required=80.0))
        items = {c["item"]: c["passed"] for c in out.pr_package["checklist"]}
        assert "confidence_alignment" in items
        assert items["confidence_alignment"] is True

    def test_pr_checklist_confidence_alignment_false_when_misaligned(self):
        report = _make_report(confidence_score=70.0)
        out = self._run(report, _make_mission(confidence_required=85.0))
        items = {c["item"]: c["passed"] for c in out.pr_package["checklist"]}
        assert items["confidence_alignment"] is False

    def test_pr_checklist_validation_signal_item_present(self):
        report = _make_report(normalized=[])
        out = self._run(report, _make_mission())
        items = {c["item"]: c["passed"] for c in out.pr_package["checklist"]}
        assert "validation_signal" in items

    def test_pr_quality_score_matches_report_score(self):
        report = _make_report(score=81.5)
        out = self._run(report, _make_mission())
        assert out.pr_package["quality_score"] == 81.5


# ---------------------------------------------------------------------------
# TestSuggestBeadStage — _suggest_bead() creation logic
# ---------------------------------------------------------------------------


class TestSuggestBeadStage:
    """Verify bead suggestion rules."""

    def _run(self, report: MagnetReport, mission: dict) -> AgentLeadOutput:
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        return _run_with_mock_sc(lead, mission, [])

    def test_proceed_produces_no_bead(self):
        report = _make_report(score=92.0, recommendation="proceed")
        out = self._run(report, _make_mission(confidence_required=0.0))
        assert out.suggested_bead is None

    def test_proceed_reversible_only_produces_no_bead(self):
        report = _make_report(score=80.0, recommendation="proceed_reversible_only")
        out = self._run(report, _make_mission(confidence_required=0.0))
        assert out.suggested_bead is None

    def test_halt_produces_bead(self):
        report = _make_report(score=30.0, recommendation="halt")
        out = self._run(report, _make_mission())
        assert out.suggested_bead is not None

    def test_replan_produces_bead(self):
        report = _make_report(
            score=62.0,
            confidence_score=62.0,
            recommendation="replan",
        )
        out = self._run(report, _make_mission(confidence_required=0.0))
        assert out.suggested_bead is not None

    def test_review_produces_bead_when_called_directly(self):
        """_suggest_bead() with 'review' decision produces a bead.

        'review' is not reachable from _recommend() in normal pipeline flow
        (decision_from_score() requires human_gate_required=True), so we call
        _suggest_bead() directly to cover the branch.
        """
        mock_orch = MagicMock()
        mock_orch.process.return_value = _make_report()
        lead = AgentLead(orchestrator=mock_orch)
        report = _make_report(mission_id="CHR-REV", feedback=["needs review"])
        recommendation = {"decision": "review"}
        bead = lead._suggest_bead(_make_mission(mission_id="CHR-REV"), recommendation, report)
        assert bead is not None
        assert bead["source"] == "agent_lead"

    def test_halt_bead_has_p0_priority(self):
        report = _make_report(score=30.0, recommendation="halt")
        out = self._run(report, _make_mission())
        assert out.suggested_bead["priority"] == "p0"

    def test_replan_bead_has_p1_priority(self):
        report = _make_report(
            score=62.0,
            confidence_score=62.0,
            recommendation="replan",
        )
        out = self._run(report, _make_mission(confidence_required=0.0))
        assert out.suggested_bead["priority"] == "p1"

    def test_bead_title_contains_objective(self):
        report = _make_report(score=30.0, recommendation="halt")
        mission = _make_mission(objective="Deploy hotfix to staging")
        out = self._run(report, mission)
        assert "Deploy hotfix to staging" in out.suggested_bead["title"]

    def test_bead_title_truncates_objective_at_60_chars(self):
        long_obj = "X" * 80
        mission = _make_mission(objective=long_obj)
        report = _make_report(score=30.0, recommendation="halt")
        out = self._run(report, mission)
        # Title is "Agent Lead follow-up: " + 60 chars
        assert len(out.suggested_bead["title"]) <= 22 + 60

    def test_bead_source_is_agent_lead(self):
        report = _make_report(score=30.0, recommendation="halt")
        out = self._run(report, _make_mission())
        assert out.suggested_bead["source"] == "agent_lead"

    def test_bead_mission_id_matches_mission(self):
        report = _make_report(mission_id="CHR-BEAD-ID")
        mission = _make_mission(mission_id="CHR-BEAD-ID")
        # Force non-proceed decision
        report = _make_report(
            mission_id="CHR-BEAD-ID",
            score=30.0,
            recommendation="halt",
        )
        out = self._run(report, mission)
        assert out.suggested_bead["mission_id"] == "CHR-BEAD-ID"

    def test_bead_objective_mentions_decision(self):
        report = _make_report(score=30.0, recommendation="halt")
        out = self._run(report, _make_mission())
        assert "halt" in out.suggested_bead["objective"]

    def test_bead_objective_includes_findings(self):
        report = _make_report(
            score=30.0,
            recommendation="halt",
            feedback=["Secret exposure detected", "Risk elevated"],
        )
        out = self._run(report, _make_mission())
        obj = out.suggested_bead["objective"]
        assert "Secret exposure detected" in obj


# ---------------------------------------------------------------------------
# TestHandoffPrepStage — _handoff_prep() logic
# ---------------------------------------------------------------------------


class TestHandoffPrepStage:
    """Verify the handoff prep document."""

    def _run(self, report: MagnetReport, mission: dict) -> AgentLeadOutput:
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        return _run_with_mock_sc(lead, mission, [])

    def test_handoff_directive_summary_non_empty(self):
        report = _make_report()
        out = self._run(report, _make_mission())
        assert out.handoff_prep["directive_summary"]

    def test_handoff_next_session_goals_non_empty(self):
        report = _make_report()
        out = self._run(report, _make_mission())
        assert len(out.handoff_prep["next_session_goals"]) > 0

    def test_handoff_decision_echoed(self):
        report = _make_report(score=30.0, recommendation="halt")
        out = self._run(report, _make_mission())
        assert out.handoff_prep["decision"] == "halt"

    def test_handoff_audit_log_ref_is_mission_id(self):
        report = _make_report()
        mission = _make_mission(mission_id="CHR-HANDOFF-REF")
        out = self._run(report, mission)
        assert out.handoff_prep["audit_log_ref"] == "CHR-HANDOFF-REF"


# ---------------------------------------------------------------------------
# TestRunOrchestration — orchestrator.process() delegation
# ---------------------------------------------------------------------------


class TestRunOrchestration:
    """Verify run() delegates correctly to orchestrator.process()."""

    def test_orchestrator_process_called_when_no_report(self):
        mock_orch = MagicMock()
        mock_orch.process.return_value = _make_report(mission_id="CHR-PROC")
        lead = AgentLead(orchestrator=mock_orch)
        mission = _make_mission(mission_id="CHR-PROC")
        _run_with_mock_sc(lead, mission, [])
        mock_orch.process.assert_called_once_with("CHR-PROC", [])

    def test_orchestrator_process_not_called_when_report_supplied(self):
        mock_orch = MagicMock()
        report = _make_report(mission_id="CHR-SKIP")
        lead = AgentLead(orchestrator=mock_orch)
        mission = _make_mission(mission_id="CHR-SKIP")

        mock_sc = MagicMock()
        original = _AL_MOD._load_local

        def _patched(name, filename):
            if filename == "session_compact.py":
                return mock_sc
            return original(name, filename)

        with patch.object(_AL_MOD, "_load_local", side_effect=_patched):
            lead.run(mission, [], report=report)

        mock_orch.process.assert_not_called()

    def test_run_passes_events_to_orchestrator(self):
        mock_orch = MagicMock()
        mock_orch.process.return_value = _make_report()
        lead = AgentLead(orchestrator=mock_orch)
        events = [
            MagnetEvent("CHR-TEST", "scope_magnet", "validation", {"x": 1}),
            MagnetEvent("CHR-TEST", "security_magnet", "execution", {"y": 2}),
        ]
        _run_with_mock_sc(lead, _make_mission(), events)
        call_events = mock_orch.process.call_args[0][1]
        assert len(call_events) == 2


# ---------------------------------------------------------------------------
# TestSessionCompactIntegration — graceful failure handling
# ---------------------------------------------------------------------------


class TestSessionCompactIntegration:
    """Verify session_compact errors are silently swallowed."""

    def test_run_succeeds_even_when_session_compact_raises(self):
        mock_orch = MagicMock()
        mock_orch.process.return_value = _make_report()
        lead = AgentLead(orchestrator=mock_orch)
        mission = _make_mission(mission_id="CHR-SC-ERR")
        original = _AL_MOD._load_local

        def _patched(name, filename):
            if filename == "session_compact.py":
                raise ImportError("session_compact unavailable in test")
            return original(name, filename)

        with patch.object(_AL_MOD, "_load_local", side_effect=_patched):
            out = lead.run(mission, [])

        assert out is not None
        assert out.decision in ("proceed", "proceed_reversible_only", "replan", "halt", "review")

    def test_session_compact_write_handoff_called_with_mission(self):
        mock_orch = MagicMock()
        mock_orch.process.return_value = _make_report(mission_id="CHR-SC-OK")
        lead = AgentLead(orchestrator=mock_orch)
        mission = _make_mission(mission_id="CHR-SC-OK")

        mock_sc = MagicMock()
        original = _AL_MOD._load_local

        def _patched(name, filename):
            if filename == "session_compact.py":
                return mock_sc
            return original(name, filename)

        with patch.object(_AL_MOD, "_load_local", side_effect=_patched):
            lead.run(mission, [])

        mock_sc.write_handoff.assert_called_once()
        call_kwargs = mock_sc.write_handoff.call_args
        assert call_kwargs[1]["agent"] == "agent_lead"
        assert call_kwargs[1]["mission"] == mission


# ---------------------------------------------------------------------------
# TestMissionDefaults — missing / default keys in the mission dict
# ---------------------------------------------------------------------------


class TestMissionDefaults:
    """Verify graceful handling of minimal or missing mission fields."""

    def _run(self, mission: dict, report: MagnetReport | None = None) -> AgentLeadOutput:
        report = report or _make_report()
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        return _run_with_mock_sc(lead, mission, [])

    def test_missing_mission_id_uses_unknown(self):
        out = self._run({"objective": "do stuff", "confidence_required": 75.0})
        # orchestrator.process called with mission_id="unknown"
        assert out.audit_log["mission_id"] is None  # mission.get("mission_id") = None

    def test_missing_objective_defaults_empty_string(self):
        out = self._run({"mission_id": "CHR-NOOBJ"})
        assert out.final_report["objective"] == ""

    def test_missing_confidence_required_defaults_75(self):
        report = _make_report(confidence_score=76.0)
        out = self._run({"mission_id": "CHR-NOCONF"}, report=report)
        # Default is 75.0; confidence_score=76 >= 75 → alignment True
        assert out.final_report["evaluation"]["alignment_with_required"] is True

    def test_missing_autonomy_level_defaults_l1_in_handoff(self):
        out = self._run({"mission_id": "CHR-NOAUTO"})
        assert out.handoff_prep["context_snapshot"]["autonomy_level"] == "L1"


# ---------------------------------------------------------------------------
# TestParametrizedEndToEnd — cross-cutting parametrized scenarios
# ---------------------------------------------------------------------------


class TestParametrizedEndToEnd:
    """Parametrized end-to-end scenarios through the full pipeline."""

    @pytest.mark.parametrize(
        "score,confidence_score,required,magnet_recommendation,expected_decision",
        [
            # Proceed: high score, alignment OK, magnet says proceed
            (92.0, 92.0, 75.0, "proceed", "proceed"),
            # Proceed reversible: mid-high score, alignment OK
            (82.0, 82.0, 75.0, "proceed_reversible_only", "proceed_reversible_only"),
            # Replan: good score but confidence misaligned
            (82.0, 70.0, 80.0, "proceed_reversible_only", "replan"),
            # Halt override: regardless of score
            (95.0, 95.0, 75.0, "halt", "halt"),
            # Halt via alignment failure + low score
            (45.0, 45.0, 75.0, "replan", "replan"),
        ],
    )
    def test_full_pipeline_decision(
        self,
        score,
        confidence_score,
        required,
        magnet_recommendation,
        expected_decision,
    ):
        report = _make_report(
            score=score,
            confidence_score=confidence_score,
            recommendation=magnet_recommendation,
        )
        mission = _make_mission(confidence_required=required)
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        out = _run_with_mock_sc(lead, mission, [])
        assert out.decision == expected_decision

    @pytest.mark.parametrize(
        "decision,expect_bead",
        [
            ("proceed", False),
            ("proceed_reversible_only", False),
            ("replan", True),
            ("halt", True),
            # "review" excluded: not reachable from _recommend() in normal flow;
            # tested directly in TestSuggestBeadStage.test_review_produces_bead_when_called_directly
        ],
    )
    def test_bead_created_iff_not_proceeding(self, decision, expect_bead):
        score_map = {
            "proceed": 92.0,
            "proceed_reversible_only": 80.0,
            "replan": 62.0,
            "halt": 30.0,
        }
        report = _make_report(
            score=score_map[decision],
            confidence_score=score_map[decision],
            recommendation=decision,
        )
        out_mock = MagicMock()
        out_mock.process.return_value = report
        lead = AgentLead(orchestrator=out_mock)
        out = _run_with_mock_sc(lead, _make_mission(confidence_required=0.0), [])
        if expect_bead:
            assert out.suggested_bead is not None
        else:
            assert out.suggested_bead is None

    @pytest.mark.parametrize("event_count", [0, 1, 5, 20])
    def test_audit_log_event_count_matches_events_list(self, event_count):
        events = [MagnetEvent("CHR-CNT", "scope_magnet", "validation", {}) for _ in range(event_count)]
        report = _make_report()
        mock_orch = MagicMock()
        mock_orch.process.return_value = report
        lead = AgentLead(orchestrator=mock_orch)
        out = _run_with_mock_sc(lead, _make_mission(), events)
        assert out.audit_log["event_count"] == event_count
