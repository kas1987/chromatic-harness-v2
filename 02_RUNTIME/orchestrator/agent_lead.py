"""Agent Lead — SYNTHESIZE → EVALUATE → RECOMMEND → REPORT → HANDOFF PREP."""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import dataclass
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
_RUNTIME = os.path.dirname(_HERE)
if _RUNTIME not in sys.path:
    sys.path.insert(0, _RUNTIME)


def _load_local(name: str, filename: str):
    path = os.path.join(_HERE, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_conf_mod = _load_local("confidence_engine", "confidence_engine.py")
decision_from_score = _conf_mod.decision_from_score

from magnets.base_magnet import MagnetEvent  # noqa: E402
from magnets.magnet_orchestrator import MagnetOrchestrator, MagnetReport  # noqa: E402


@dataclass
class AgentLeadOutput:
    final_report: dict[str, Any]
    pr_package: dict[str, Any]
    next_steps: dict[str, Any]
    audit_log: dict[str, Any]
    handoff_prep: dict[str, Any]
    suggested_bead: dict[str, Any] | None = None
    decision: str = "review"
    composite_score: float = 0.0


class AgentLead:
    """Correlates magnet evidence and produces structured mission outputs."""

    def __init__(self, orchestrator: MagnetOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or MagnetOrchestrator()

    def run(
        self,
        mission: dict[str, Any],
        events: list[MagnetEvent | dict[str, Any]],
        report: MagnetReport | None = None,
    ) -> AgentLeadOutput:
        mission_id = mission.get("mission_id", "unknown")
        report = report or self.orchestrator.process(mission_id, events)

        synthesized = self._synthesize(mission, report)
        evaluation = self._evaluate(mission, report, synthesized)
        recommendation = self._recommend(evaluation, report)
        final_report = self._report(
            mission, report, synthesized, evaluation, recommendation
        )
        handoff = self._handoff_prep(mission, report, recommendation, final_report)
        pr_package = self._pr_package(mission, evaluation, recommendation)
        next_steps = self._next_steps(mission, recommendation, report)
        audit_log = self._audit_log(mission, report, events)
        suggested_bead = self._suggest_bead(mission, recommendation, report)

        return AgentLeadOutput(
            final_report=final_report,
            pr_package=pr_package,
            next_steps=next_steps,
            audit_log=audit_log,
            handoff_prep=handoff,
            suggested_bead=suggested_bead,
            decision=recommendation["decision"],
            composite_score=report.score,
        )

    def _synthesize(
        self, mission: dict[str, Any], report: MagnetReport
    ) -> dict[str, Any]:
        return {
            "mission_id": mission.get("mission_id"),
            "objective": mission.get("objective", ""),
            "event_count": report.collected_count,
            "magnets_seen": report.correlated.get("magnets_seen", []),
            "key_findings": report.feedback,
            "risk_summary": report.correlated.get("total_risk_delta", 0.0),
            "confidence_summary": report.correlated.get("total_confidence_delta", 0.0),
        }

    def _evaluate(
        self,
        mission: dict[str, Any],
        report: MagnetReport,
        synthesized: dict[str, Any],
    ) -> dict[str, Any]:
        required = float(mission.get("confidence_required", 75.0))
        alignment = report.confidence_score >= required
        validation_events = [
            e
            for e in report.normalized
            if e.magnet_name == "validation_magnet"
            or e.inflection_point == "validation"
        ]
        tests_ok = not any(
            "fail" in ev.lower() for e in validation_events for ev in e.evidence
        )
        return {
            "quality_score": report.score,
            "confidence_score": report.confidence_score,
            "risk_score": report.risk_score,
            "alignment_with_required": alignment,
            "required_confidence": required,
            "validation_events": len(validation_events),
            "tests_passing_signal": tests_ok,
        }

    def _recommend(
        self, evaluation: dict[str, Any], report: MagnetReport
    ) -> dict[str, Any]:
        decision = decision_from_score(evaluation["quality_score"])
        if report.recommendation == "halt":
            decision = "halt"
        elif not evaluation["alignment_with_required"]:
            decision = "replan"
        return {
            "decision": decision,
            "magnet_recommendation": report.recommendation,
            "rationale": report.feedback or ["No significant findings."],
        }

    def _report(
        self,
        mission: dict[str, Any],
        report: MagnetReport,
        synthesized: dict[str, Any],
        evaluation: dict[str, Any],
        recommendation: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "executive_summary": (
                f"Mission {mission.get('mission_id')} scored {report.score}/100 "
                f"with decision '{recommendation['decision']}'."
            ),
            "objective": mission.get("objective", ""),
            "synthesis": synthesized,
            "evaluation": evaluation,
            "recommendation": recommendation,
            "achievements": [
                f"Processed {report.collected_count} magnet events",
                f"Confidence {report.confidence_score}%",
            ],
            "findings": report.feedback,
        }

    def _pr_package(
        self,
        mission: dict[str, Any],
        evaluation: dict[str, Any],
        recommendation: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "title": f"[Agent Lead] {mission.get('objective', 'Mission')[:80]}",
            "ready_for_review": recommendation["decision"]
            in ("proceed", "proceed_reversible_only"),
            "quality_score": evaluation["quality_score"],
            "checklist": [
                {
                    "item": "confidence_alignment",
                    "passed": evaluation["alignment_with_required"],
                },
                {
                    "item": "validation_signal",
                    "passed": evaluation["tests_passing_signal"],
                },
            ],
        }

    def _next_steps(
        self,
        mission: dict[str, Any],
        recommendation: dict[str, Any],
        report: MagnetReport,
    ) -> dict[str, Any]:
        decision = recommendation["decision"]
        actions: list[str] = []
        if decision == "proceed":
            actions.append("Auto-proceed with next mission phase.")
        elif decision == "proceed_reversible_only":
            actions.append("Proceed with reversible, bounded changes only.")
        elif decision == "replan":
            actions.append("Replan mission scope and re-run discovery.")
        elif decision == "halt":
            actions.append("Halt mission and escalate to human reviewer.")
        else:
            actions.append("Create review package for human gate.")
        if report.correlated.get("escalations", 0) > 0:
            actions.append("Address escalated magnet findings before continuing.")
        return {
            "decision": decision,
            "priority": "p0" if decision == "halt" else "p2",
            "actions": actions,
            "objective": mission.get("objective", ""),
        }

    def _audit_log(
        self,
        mission: dict[str, Any],
        report: MagnetReport,
        events: list[MagnetEvent | dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "mission_id": mission.get("mission_id"),
            "event_count": len(events),
            "magnets_seen": report.correlated.get("magnets_seen", []),
            "total_risk_delta": report.correlated.get("total_risk_delta", 0.0),
            "total_confidence_delta": report.correlated.get(
                "total_confidence_delta", 0.0
            ),
            "gold_artifact_ref": report.gold_artifact,
        }

    def _handoff_prep(
        self,
        mission: dict[str, Any],
        report: MagnetReport,
        recommendation: dict[str, Any],
        final_report: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "directive_summary": final_report["executive_summary"],
            "context_snapshot": {
                "mission_id": mission.get("mission_id"),
                "objective": mission.get("objective", ""),
                "autonomy_level": mission.get("autonomy_level", "L1"),
                "composite_score": report.score,
            },
            "next_session_goals": [
                a for a in self._next_steps(mission, recommendation, report)["actions"]
            ],
            "audit_log_ref": mission.get("mission_id"),
            "decision": recommendation["decision"],
        }

    def _suggest_bead(
        self,
        mission: dict[str, Any],
        recommendation: dict[str, Any],
        report: MagnetReport,
    ) -> dict[str, Any] | None:
        if recommendation["decision"] in ("proceed", "proceed_reversible_only"):
            return None
        title = f"Agent Lead follow-up: {mission.get('objective', 'mission')[:60]}"
        return {
            "title": title,
            "objective": (
                f"Address {recommendation['decision']} decision for "
                f"{mission.get('mission_id')}. Findings: {'; '.join(report.feedback[:3])}"
            ),
            "priority": "p0" if recommendation["decision"] == "halt" else "p1",
            "source": "agent_lead",
            "mission_id": mission.get("mission_id"),
        }
