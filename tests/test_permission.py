"""Tests for permission.py — action allow/deny logic and role checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading via importlib so the test works regardless of install state
# ---------------------------------------------------------------------------
_RUNTIME = Path(__file__).resolve().parent.parent / "02_RUNTIME"

def _load(name: str, rel: str):
    path = _RUNTIME / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# Load dependency first, then the module under test
_git_policy = _load("workflows.git_policy", "workflows/git_policy.py")
_perm = _load("workflows.permission", "workflows/permission.py")

Action = _perm.Action
check_permission = _perm.check_permission
PermissionResult = _perm.PermissionResult
_path_in_allowed = _perm._path_in_allowed


class TestPermission:
    # ------------------------------------------------------------------
    # _path_in_allowed helper
    # ------------------------------------------------------------------

    def test_path_in_allowed_exact_match(self):
        assert _path_in_allowed("src/foo.py", ["src/foo.py"]) is True

    def test_path_in_allowed_prefix_match(self):
        assert _path_in_allowed("src/utils/helpers.py", ["src/utils"]) is True

    def test_path_in_allowed_no_match(self):
        assert _path_in_allowed("other/module.py", ["src/utils"]) is False

    def test_path_in_allowed_empty_list(self):
        assert _path_in_allowed("any/path.py", []) is False

    def test_path_in_allowed_backslash_normalised(self):
        assert _path_in_allowed("src\\utils\\mod.py", ["src/utils"]) is True

    # ------------------------------------------------------------------
    # READ actions (always allowed)
    # ------------------------------------------------------------------

    def test_read_assigned_no_path_restriction(self):
        r = check_permission(Action.READ_ASSIGNED, confidence=50.0)
        assert r.allowed is True

    def test_read_assigned_path_in_allowed(self):
        r = check_permission(
            Action.READ_ASSIGNED,
            confidence=80.0,
            allowed_files=["src/mod.py"],
            target_path="src/mod.py",
        )
        assert r.allowed is True

    def test_read_assigned_path_outside_allowed(self):
        r = check_permission(
            Action.READ_ASSIGNED,
            confidence=80.0,
            allowed_files=["src/mod.py"],
            target_path="other/mod.py",
        )
        assert r.allowed is False

    def test_read_unrelated_always_allowed(self):
        r = check_permission(Action.READ_UNRELATED, confidence=10.0)
        assert r.allowed is True

    # ------------------------------------------------------------------
    # EDIT_ASSIGNED
    # ------------------------------------------------------------------

    def test_edit_assigned_low_confidence_denied(self):
        r = check_permission(Action.EDIT_ASSIGNED, confidence=60.0)
        assert r.allowed is False
        assert "confidence" in r.reason

    def test_edit_assigned_high_confidence_allowed(self):
        r = check_permission(Action.EDIT_ASSIGNED, confidence=80.0)
        assert r.allowed is True

    def test_edit_assigned_path_not_allowed(self):
        r = check_permission(
            Action.EDIT_ASSIGNED,
            confidence=90.0,
            allowed_files=["src/a.py"],
            target_path="src/b.py",
        )
        assert r.allowed is False

    def test_edit_unassigned_always_denied(self):
        r = check_permission(Action.EDIT_UNASSIGNED, confidence=99.0)
        assert r.allowed is False
        assert "unassigned" in r.reason

    # ------------------------------------------------------------------
    # GIT_COMMIT
    # ------------------------------------------------------------------

    def test_git_commit_below_threshold_denied(self):
        r = check_permission(
            Action.GIT_COMMIT,
            confidence=70.0,
            verifier_approved=True,
        )
        assert r.allowed is False

    def test_git_commit_no_verifier_denied(self):
        r = check_permission(
            Action.GIT_COMMIT,
            confidence=90.0,
            verifier_approved=False,
        )
        assert r.allowed is False
        assert "verifier" in r.reason

    def test_git_commit_critical_risk_denied(self):
        r = check_permission(
            Action.GIT_COMMIT,
            confidence=90.0,
            verifier_approved=True,
            risk_level="critical",
        )
        assert r.allowed is False
        assert r.requires_human is True

    def test_git_commit_allowed(self):
        r = check_permission(
            Action.GIT_COMMIT,
            confidence=90.0,
            verifier_approved=True,
            risk_level="low",
        )
        assert r.allowed is True

    # ------------------------------------------------------------------
    # GIT_PUSH
    # ------------------------------------------------------------------

    def test_git_push_tests_not_passed_denied(self):
        r = check_permission(
            Action.GIT_PUSH,
            confidence=95.0,
            verifier_approved=True,
            tests_passed=False,
            risk_level="low",
        )
        assert r.allowed is False
        assert "tests" in r.reason

    def test_git_push_high_risk_denied(self):
        r = check_permission(
            Action.GIT_PUSH,
            confidence=95.0,
            verifier_approved=True,
            tests_passed=True,
            risk_level="high",
        )
        assert r.allowed is False
        assert r.requires_human is True

    def test_git_push_allowed(self):
        r = check_permission(
            Action.GIT_PUSH,
            confidence=95.0,
            verifier_approved=True,
            tests_passed=True,
            risk_level="low",
        )
        assert r.allowed is True

    # ------------------------------------------------------------------
    # GIT_MERGE
    # ------------------------------------------------------------------

    def test_git_merge_no_ci_denied(self):
        r = check_permission(
            Action.GIT_MERGE,
            confidence=99.0,
            verifier_approved=True,
            tests_passed=True,
            ci_passed=False,
            risk_level="low",
        )
        assert r.allowed is False
        assert "CI" in r.reason

    def test_git_merge_medium_risk_denied(self):
        r = check_permission(
            Action.GIT_MERGE,
            confidence=99.0,
            verifier_approved=True,
            tests_passed=True,
            ci_passed=True,
            risk_level="medium",
        )
        assert r.allowed is False
        assert r.requires_human is True

    def test_git_merge_allowed(self):
        r = check_permission(
            Action.GIT_MERGE,
            confidence=99.0,
            verifier_approved=True,
            tests_passed=True,
            ci_passed=True,
            risk_level="low",
        )
        assert r.allowed is True

    # ------------------------------------------------------------------
    # Destructive / secrets actions
    # ------------------------------------------------------------------

    def test_delete_requires_human(self):
        r = check_permission(Action.DELETE, confidence=99.0)
        assert r.allowed is False
        assert r.requires_human is True

    def test_touch_secrets_denied(self):
        r = check_permission(Action.TOUCH_SECRETS, confidence=99.0)
        assert r.allowed is False

    def test_install_packages_requires_human(self):
        r = check_permission(Action.INSTALL_PACKAGES, confidence=99.0)
        assert r.allowed is False
        assert r.requires_human is True

    def test_run_tests_always_allowed(self):
        r = check_permission(Action.RUN_TESTS, confidence=0.0)
        assert r.allowed is True

    def test_change_config_requires_human(self):
        r = check_permission(Action.CHANGE_CONFIG, confidence=99.0)
        assert r.allowed is False
        assert r.requires_human is True

    # ------------------------------------------------------------------
    # GIT_PR_REVIEW
    # ------------------------------------------------------------------

    def test_git_pr_review_denied_when_push_denied(self):
        """PR review must be denied when push pre-conditions fail."""
        r = check_permission(
            Action.GIT_PR_REVIEW,
            confidence=95.0,
            verifier_approved=True,
            tests_passed=False,
            risk_level="low",
        )
        assert r.allowed is False

    def test_git_pr_review_allowed(self):
        r = check_permission(
            Action.GIT_PR_REVIEW,
            confidence=99.0,
            verifier_approved=True,
            tests_passed=True,
            risk_level="low",
        )
        assert r.allowed is True

    # ------------------------------------------------------------------
    # PUSH_MERGE_DEPLOY
    # ------------------------------------------------------------------

    def test_push_merge_deploy_denied_when_not_ready(self):
        r = check_permission(
            Action.PUSH_MERGE_DEPLOY,
            confidence=50.0,
            verifier_approved=False,
            tests_passed=False,
        )
        assert r.allowed is False
        assert r.requires_human is True

    def test_rename_major_requires_human(self):
        r = check_permission(Action.RENAME_MAJOR, confidence=99.0)
        assert r.allowed is False
        assert r.requires_human is True
