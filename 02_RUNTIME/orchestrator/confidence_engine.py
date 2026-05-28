"""Confidence scoring skeleton."""

from dataclasses import dataclass


@dataclass
class ConfidenceInputs:
    objective_clarity: float
    scope_clarity: float
    evidence_quality: float
    reversibility: float
    tool_fit: float
    risk_awareness: float
    testability: float


def score_confidence(inputs: ConfidenceInputs) -> float:
    return round(
        inputs.objective_clarity * 0.20
        + inputs.scope_clarity * 0.20
        + inputs.evidence_quality * 0.20
        + inputs.reversibility * 0.10
        + inputs.tool_fit * 0.10
        + inputs.risk_awareness * 0.10
        + inputs.testability * 0.10,
        2,
    )


def decision_from_score(score: float, human_gate_required: bool = False) -> str:
    if human_gate_required:
        return "review"
    if score >= 90:
        return "proceed"
    if score >= 75:
        return "proceed_reversible_only"
    if score >= 60:
        return "replan"
    if score >= 40:
        return "review"
    return "halt"
