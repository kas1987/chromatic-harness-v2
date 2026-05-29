"""Verifier gate — review worker output before promotion."""

from __future__ import annotations

from workflows.models import TaskNode, VerifierResult


def verify_task_completion(
    task: TaskNode,
    *,
    files_touched: list[str],
    confidence_score: float,
    risk_level: str,
    tools_used: int,
    validation: str = "",
    human_gate_bypassed: bool = False,
    verifier: str = "sonnet",
) -> VerifierResult:
    issues: list[str] = []
    required_fixes: list[str] = []

    if confidence_score <= 0:
        issues.append("confidence score not recorded")
    if not risk_level:
        issues.append("risk level not recorded")
    if tools_used > task.tool_budget:
        issues.append(f"tool budget exceeded ({tools_used} > {task.tool_budget})")
    if human_gate_bypassed:
        issues.append("human gate bypass detected")

    for path in files_touched:
        if task.allowed_files and path not in task.allowed_files:
            norm = path.replace("\\", "/")
            allowed = any(
                norm == a.replace("\\", "/") or norm.startswith(a.rstrip("/") + "/")
                for a in task.allowed_files
            )
            if not allowed:
                issues.append(f"file outside scope: {path}")

    for forbidden in task.forbidden_files:
        if forbidden in files_touched:
            issues.append(f"forbidden file touched: {forbidden}")

    if task.acceptance_criteria and not validation:
        issues.append("validation not performed")

    if issues:
        decision = "reject" if any("forbidden" in i or "bypass" in i for i in issues) else "request_changes"
        return VerifierResult(
            task_id=task.task_id,
            verifier=verifier,
            decision=decision,
            confidence=confidence_score,
            issues=issues,
            required_fixes=issues,
            next_task=task.task_id if decision != "approve" else "",
        )

    return VerifierResult(
        task_id=task.task_id,
        verifier=verifier,
        decision="approve",
        confidence=confidence_score,
        next_task="",
    )
