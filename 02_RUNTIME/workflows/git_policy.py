"""Confidence thresholds and evaluation for git operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# PDR-aligned tiers; merge requires highest bar
THRESHOLD_COMMIT = 75
THRESHOLD_PUSH = 88
THRESHOLD_PR_REVIEW = 85
THRESHOLD_MERGE = 95

BLOCKED_RISK_FOR_PUSH = {"high", "critical"}
BLOCKED_RISK_FOR_MERGE = {"medium", "high", "critical"}


class GitOperation(str, Enum):
    COMMIT = "commit"
    PUSH = "push"
    OPEN_PR = "open_pr"
    MERGE = "merge"


@dataclass
class GitPipelineDecision:
    commit: bool
    push: bool
    open_pr: bool
    merge: bool
    reasons: dict[str, str]

    def to_dict(self) -> dict:
        return {
            "commit": self.commit,
            "push": self.push,
            "open_pr": self.open_pr,
            "merge": self.merge,
            "reasons": self.reasons,
            "thresholds": {
                "commit": THRESHOLD_COMMIT,
                "push": THRESHOLD_PUSH,
                "open_pr": THRESHOLD_PR_REVIEW,
                "merge": THRESHOLD_MERGE,
            },
        }


def evaluate_git_pipeline(
    *,
    confidence: float,
    risk_level: str = "low",
    verifier_approved: bool = False,
    tests_passed: bool = False,
    ci_passed: bool = False,
    has_staged_changes: bool = True,
    on_protected_branch: bool = False,
    secrets_detected: bool = False,
) -> GitPipelineDecision:
    """Return which git steps are allowed at the given confidence score."""
    reasons: dict[str, str] = {}
    risk = risk_level.lower()

    if secrets_detected:
        for op in GitOperation:
            reasons[op.value] = "secrets detected in changes"
        return GitPipelineDecision(False, False, False, False, reasons)

    commit = (
        confidence >= THRESHOLD_COMMIT
        and verifier_approved
        and has_staged_changes
        and risk != "critical"
    )
    reasons["commit"] = (
        "allowed"
        if commit
        else f"need confidence>={THRESHOLD_COMMIT}, verifier approve, staged changes, non-critical risk"
    )

    push = (
        commit
        and confidence >= THRESHOLD_PUSH
        and tests_passed
        and risk not in BLOCKED_RISK_FOR_PUSH
    )
    reasons["push"] = (
        "allowed"
        if push
        else f"need commit gate + confidence>={THRESHOLD_PUSH}, tests passed, risk not high/critical"
    )

    open_pr = (
        push
        and confidence >= THRESHOLD_PR_REVIEW
        and not on_protected_branch
    )
    reasons["open_pr"] = (
        "allowed"
        if open_pr
        else f"need push gate + confidence>={THRESHOLD_PR_REVIEW}, not on protected branch"
    )

    merge = (
        open_pr
        and confidence >= THRESHOLD_MERGE
        and ci_passed
        and risk not in BLOCKED_RISK_FOR_MERGE
    )
    reasons["merge"] = (
        "allowed"
        if merge
        else f"need PR gate + confidence>={THRESHOLD_MERGE}, CI green, low risk only"
    )

    return GitPipelineDecision(commit, push, open_pr, merge, reasons)
