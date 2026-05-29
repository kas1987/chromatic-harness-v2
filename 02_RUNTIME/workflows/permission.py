"""Permission gate — blocks unsafe mutations per PERMISSION_GATE.md."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from workflows.git_policy import (
    THRESHOLD_COMMIT,
    THRESHOLD_MERGE,
    THRESHOLD_PR_REVIEW,
    THRESHOLD_PUSH,
    BLOCKED_RISK_FOR_MERGE,
    BLOCKED_RISK_FOR_PUSH,
)


class Action(str, Enum):
    READ_ASSIGNED = "read_assigned"
    READ_UNRELATED = "read_unrelated"
    EDIT_ASSIGNED = "edit_assigned"
    EDIT_UNASSIGNED = "edit_unassigned"
    DELETE = "delete"
    RENAME_MAJOR = "rename_major"
    CHANGE_CONFIG = "change_config"
    TOUCH_SECRETS = "touch_secrets"
    RUN_TESTS = "run_tests"
    INSTALL_PACKAGES = "install_packages"
    PUSH_MERGE_DEPLOY = "push_merge_deploy"
    GIT_COMMIT = "git_commit"
    GIT_PUSH = "git_push"
    GIT_PR_REVIEW = "git_pr_review"
    GIT_MERGE = "git_merge"


@dataclass
class PermissionResult:
    allowed: bool
    reason: str
    requires_human: bool = False


def _path_in_allowed(path: str, allowed_files: Iterable[str]) -> bool:
    allowed = list(allowed_files)
    if not allowed:
        return False
    norm = path.replace("\\", "/")
    for pattern in allowed:
        p = pattern.replace("\\", "/")
        if norm == p or norm.startswith(p.rstrip("/") + "/"):
            return True
    return False


def check_permission(
    action: Action,
    *,
    confidence: float,
    allowed_files: list[str] | None = None,
    target_path: str = "",
    risk_level: str = "low",
    verifier_approved: bool = False,
    tests_passed: bool = False,
    ci_passed: bool = False,
) -> PermissionResult:
    """Evaluate whether an action is permitted under the workflow permission gate."""
    allowed_files = allowed_files or []

    if action == Action.READ_ASSIGNED:
        if not allowed_files or _path_in_allowed(target_path, allowed_files):
            return PermissionResult(True, "read assigned or no path check")
        return PermissionResult(False, "path not in allowed_files")

    if action == Action.READ_UNRELATED:
        return PermissionResult(True, "read allowed with justification")

    if action == Action.EDIT_ASSIGNED:
        if confidence < 75:
            return PermissionResult(False, "confidence below 75 for edits")
        if allowed_files and target_path and not _path_in_allowed(target_path, allowed_files):
            return PermissionResult(False, "edit target not in allowed_files")
        return PermissionResult(True, "edit assigned permitted")

    if action == Action.EDIT_UNASSIGNED:
        return PermissionResult(False, "halt: unassigned file edit")

    if action == Action.GIT_COMMIT:
        if confidence < THRESHOLD_COMMIT:
            return PermissionResult(False, f"confidence below {THRESHOLD_COMMIT} for commit")
        if not verifier_approved:
            return PermissionResult(False, "verifier must approve before commit")
        if risk_level == "critical":
            return PermissionResult(False, "critical risk blocks auto-commit", True)
        return PermissionResult(True, "commit allowed")

    if action == Action.GIT_PUSH:
        commit = check_permission(
            Action.GIT_COMMIT,
            confidence=confidence,
            risk_level=risk_level,
            verifier_approved=verifier_approved,
        )
        if not commit.allowed:
            return commit
        if confidence < THRESHOLD_PUSH:
            return PermissionResult(False, f"confidence below {THRESHOLD_PUSH} for push")
        if not tests_passed:
            return PermissionResult(False, "tests must pass before push")
        if risk_level in BLOCKED_RISK_FOR_PUSH:
            return PermissionResult(False, f"risk {risk_level} blocks auto-push", True)
        return PermissionResult(True, "push allowed")

    if action == Action.GIT_PR_REVIEW:
        push = check_permission(
            Action.GIT_PUSH,
            confidence=confidence,
            risk_level=risk_level,
            verifier_approved=verifier_approved,
            tests_passed=tests_passed,
        )
        if not push.allowed:
            return push
        if confidence < THRESHOLD_PR_REVIEW:
            return PermissionResult(False, f"confidence below {THRESHOLD_PR_REVIEW} for PR")
        return PermissionResult(True, "PR review/open allowed")

    if action == Action.GIT_MERGE:
        pr = check_permission(
            Action.GIT_PR_REVIEW,
            confidence=confidence,
            risk_level=risk_level,
            verifier_approved=verifier_approved,
            tests_passed=tests_passed,
        )
        if not pr.allowed:
            return pr
        if confidence < THRESHOLD_MERGE:
            return PermissionResult(False, f"confidence below {THRESHOLD_MERGE} for merge", True)
        if not ci_passed:
            return PermissionResult(False, "CI must pass before merge")
        if risk_level in BLOCKED_RISK_FOR_MERGE:
            return PermissionResult(False, f"risk {risk_level} blocks auto-merge", True)
        return PermissionResult(True, "merge allowed")

    if action in (
        Action.DELETE,
        Action.RENAME_MAJOR,
        Action.CHANGE_CONFIG,
        Action.INSTALL_PACKAGES,
        Action.PUSH_MERGE_DEPLOY,
    ):
        return PermissionResult(False, f"{action.value} requires human approval", True)

    if action == Action.TOUCH_SECRETS:
        return PermissionResult(False, "halt: secrets/env/auth")

    if action == Action.RUN_TESTS:
        return PermissionResult(True, "tests allowed")

    if risk_level == "critical" and action == Action.EDIT_ASSIGNED:
        return PermissionResult(False, "critical risk requires human gate", True)

    return PermissionResult(False, f"unknown action: {action.value}")
