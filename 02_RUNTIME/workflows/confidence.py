"""Confidence scoring bridge to orchestrator.confidence_engine."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[1]
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from orchestrator.confidence_engine import (  # noqa: E402
    ConfidenceInputs,
    decision_from_score,
    score_confidence,
)
from workflows.models import ConfidenceRecord, WorkflowDecision

# CMP decision -> PDR workflow decision
_CMP_TO_WORKFLOW: dict[str, WorkflowDecision] = {
    "proceed": WorkflowDecision.EXECUTE,
    "proceed_reversible_only": WorkflowDecision.EXECUTE,
    "replan": WorkflowDecision.PLAN_ONLY,
    "review": WorkflowDecision.PLAN_ONLY,
    "halt": WorkflowDecision.HALT,
}


def score_task(
    *,
    objective_clarity: float = 70.0,
    scope_clarity: float = 70.0,
    evidence_quality: float = 70.0,
    reversibility: float = 80.0,
    tool_fit: float = 80.0,
    risk_awareness: float = 70.0,
    testability: float = 70.0,
    risk_level: str = "low",
    human_gate_required: bool = False,
) -> ConfidenceRecord:
    inputs = ConfidenceInputs(
        objective_clarity=objective_clarity,
        scope_clarity=scope_clarity,
        evidence_quality=evidence_quality,
        reversibility=reversibility,
        tool_fit=tool_fit,
        risk_awareness=risk_awareness,
        testability=testability,
    )
    score = score_confidence(inputs)
    cmp_decision = decision_from_score(score, human_gate_required=human_gate_required)
    workflow_decision = _CMP_TO_WORKFLOW.get(cmp_decision, WorkflowDecision.HALT)

    rev_label = "yes" if reversibility >= 80 else ("partial" if reversibility >= 50 else "no")

    return ConfidenceRecord(
        confidence_score=score,
        risk_level=risk_level,
        scope_clarity=scope_clarity,
        evidence_quality=evidence_quality,
        reversibility=rev_label,
        tool_budget_fit=tool_fit >= 60,
        cmp_decision=cmp_decision,
        workflow_decision=workflow_decision,
    )


def mutation_allowed(record: ConfidenceRecord) -> bool:
    return record.workflow_decision == WorkflowDecision.EXECUTE and record.confidence_score >= 75
