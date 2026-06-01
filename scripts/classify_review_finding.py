#!/usr/bin/env python3
"""Classify Chromatic review findings and calculate confidence scores."""
from __future__ import annotations

import re
from typing import Any, Dict, List

SECURITY = re.compile(r"\b(secret|token|password|auth|permission|sql injection|xss|csrf|vulnerability|encrypt)\b", re.I)
TEST = re.compile(r"\b(test|pytest|unit|integration|failing|coverage|assert)\b", re.I)
LINT = re.compile(r"\b(lint|format|ruff|eslint|prettier|import order|naming|style)\b", re.I)
DOCS = re.compile(r"\b(readme|docs|documentation|comment|docstring)\b", re.I)
ARCH = re.compile(r"\b(architecture|design|boundary|abstraction|coupling|refactor|module|pattern)\b", re.I)
BUG = re.compile(r"\b(bug|incorrect|wrong|fix|broken|error|exception|regression)\b", re.I)
VAGUE = re.compile(r"\b(feels|maybe|consider|unclear|not sure|seems|probably)\b", re.I)

AGENT_BY_TYPE = {
    "security": "Sentinel",
    "test_failure": "Auditor",
    "lint_style": "Janitor",
    "docs": "Archivist",
    "architecture": "Archivist",
    "bug_fix": "Sentinel",
    "repo_hygiene": "Janitor",
    "unclear": "Auditor",
}

SPECIALTIES_BY_TYPE = {
    "security": ["security", "testing", "policy"],
    "test_failure": ["testing", "observability", "python"],
    "lint_style": ["repo-hygiene", "lint", "cleanup"],
    "docs": ["docs", "contracts", "memory"],
    "architecture": ["architecture", "contracts", "governance"],
    "bug_fix": ["code-quality", "testing", "failure-modes"],
    "repo_hygiene": ["repo-hygiene", "cleanup", "boundaries"],
    "unclear": ["triage", "evidence", "clarification"],
}

ACCEPTANCE_BY_TYPE = {
    "security": ["Run targeted security/unit tests", "Confirm no secrets are exposed"],
    "test_failure": ["Re-run the failed check", "Run targeted tests"],
    "lint_style": ["Run formatter/linter for touched files"],
    "docs": ["Review rendered markdown/docs"],
    "architecture": ["Produce scoped plan or architecture note", "Do not mutate without approval"],
    "bug_fix": ["Run targeted regression test", "Run relevant lint/checks"],
    "repo_hygiene": ["Validate repo tree rules", "Confirm no broken references"],
    "unclear": ["Ask reviewer clarification or create investigation note"],
}


def classify_body(body: str, path: str | None = None) -> str:
    text = body or ""
    if SECURITY.search(text):
        return "security"
    if TEST.search(text):
        return "test_failure"
    if LINT.search(text):
        return "lint_style"
    if DOCS.search(text) or (path and path.lower().endswith((".md", ".rst", ".txt"))):
        return "docs"
    if ARCH.search(text):
        return "architecture"
    if BUG.search(text):
        return "bug_fix"
    if VAGUE.search(text):
        return "unclear"
    return "bug_fix" if path else "unclear"


def score_finding(finding: Dict[str, Any]) -> int:
    body = finding.get("body") or ""
    finding_type = finding.get("finding_type") or classify_body(body, finding.get("path"))

    actionability = 85 if finding_type not in {"unclear", "architecture"} else 55
    file_scope = 90 if finding.get("path") else 50
    testability = 80 if finding_type in {"test_failure", "bug_fix", "lint_style"} else 60
    risk_safety = 45 if finding_type == "security" else (55 if finding_type == "architecture" else 85)
    dedupe_certainty = 90 if finding.get("dedupe_key") else 40
    agent_fit = 85 if finding_type in AGENT_BY_TYPE else 50

    if VAGUE.search(body):
        actionability -= 15
        testability -= 10
    if len(body.strip()) < 20:
        actionability -= 20

    score = (
        actionability * 0.25
        + file_scope * 0.20
        + testability * 0.20
        + risk_safety * 0.15
        + dedupe_certainty * 0.10
        + agent_fit * 0.10
    )
    return max(0, min(100, int(round(score))))


def enrich_finding(finding: Dict[str, Any]) -> Dict[str, Any]:
    finding = dict(finding)
    finding_type = classify_body(finding.get("body", ""), finding.get("path"))
    finding["finding_type"] = finding_type
    finding["suggested_agent"] = AGENT_BY_TYPE.get(finding_type, "Auditor")
    finding["acceptance_checks"] = ACCEPTANCE_BY_TYPE.get(finding_type, ["Review finding manually"])
    finding["confidence_score"] = score_finding(finding)
    finding["risk_level"] = "high" if finding_type in {"security", "architecture"} else ("medium" if finding["confidence_score"] < 75 else "low")
    finding["severity"] = "high" if finding_type == "security" else ("medium" if finding_type in {"bug_fix", "test_failure", "architecture"} else "low")
    return finding


def queue_status_for_confidence(score: int, finding_type: str) -> str:
    if finding_type in {"security", "architecture"} and score < 90:
        return "needs-human-decision"
    if score >= 75:
        return "ready"
    if score >= 40:
        return "review-required"
    return "blocked"


def specialties_for_type(finding_type: str) -> List[str]:
    return SPECIALTIES_BY_TYPE.get(finding_type, ["triage"])
