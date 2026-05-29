"""Data models for the dynamic workflow runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GoMode(str, Enum):
    GO = "GO"
    GO_DEEP = "GO DEEP"
    GO_BUILD = "GO BUILD"
    GO_AUDIT = "GO AUDIT"
    GO_VERIFY = "GO VERIFY"
    GO_SWARM = "GO SWARM"
    GO_SHIP = "GO SHIP"


class WorkflowDecision(str, Enum):
    EXECUTE = "execute"
    PLAN_ONLY = "plan_only"
    HALT = "halt"


@dataclass
class TaskNode:
    task_id: str
    title: str
    assigned_model: str
    role: str
    tool_budget: int
    confidence_required: int
    risk_level: str
    status: str
    depends_on: list[str] = field(default_factory=list)
    allowed_files: list[str] = field(default_factory=list)
    forbidden_files: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskNode:
        return cls(
            task_id=data["task_id"],
            title=data["title"],
            assigned_model=data["assigned_model"],
            role=data["role"],
            tool_budget=int(data["tool_budget"]),
            confidence_required=int(data["confidence_required"]),
            risk_level=data["risk_level"],
            status=data["status"],
            depends_on=list(data.get("depends_on", [])),
            allowed_files=list(data.get("allowed_files", [])),
            forbidden_files=list(data.get("forbidden_files", [])),
            acceptance_criteria=list(data.get("acceptance_criteria", [])),
            stop_conditions=list(data.get("stop_conditions", [])),
        )


@dataclass
class TaskGraph:
    workflow_id: str
    objective: str
    risk_level: str
    tasks: list[TaskNode]
    created_at: str = ""
    global_stop_conditions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskGraph:
        return cls(
            workflow_id=data["workflow_id"],
            objective=data["objective"],
            risk_level=data["risk_level"],
            tasks=[TaskNode.from_dict(t) for t in data["tasks"]],
            created_at=data.get("created_at", ""),
            global_stop_conditions=list(data.get("global_stop_conditions", [])),
        )


@dataclass
class ConfidenceRecord:
    confidence_score: float
    risk_level: str
    scope_clarity: float
    evidence_quality: float
    reversibility: str
    tool_budget_fit: bool
    cmp_decision: str
    workflow_decision: WorkflowDecision

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence_score": self.confidence_score,
            "risk_level": self.risk_level,
            "scope_clarity": self.scope_clarity,
            "evidence_quality": self.evidence_quality,
            "reversibility": self.reversibility,
            "tool_budget_fit": self.tool_budget_fit,
            "cmp_decision": self.cmp_decision,
            "decision": self.workflow_decision.value,
        }


@dataclass
class VerifierResult:
    task_id: str
    verifier: str
    decision: str
    confidence: float
    issues: list[str] = field(default_factory=list)
    required_fixes: list[str] = field(default_factory=list)
    next_task: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "verifier": self.verifier,
            "decision": self.decision,
            "confidence": self.confidence,
            "issues": self.issues,
            "required_fixes": self.required_fixes,
            "next_task": self.next_task,
        }
