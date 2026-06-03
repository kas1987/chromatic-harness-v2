"""Tests for workflows.permission — permission gate decisions."""

from __future__ import annotations

import pytest

from workflows.permission import Action, PermissionResult, _path_in_allowed, check_permission
from workflows.git_policy import THRESHOLD_COMMIT, THRESHOLD_PUSH, THRESHOLD_MERGE


# ── _path_in_allowed helper ───────────────────────────────────────────────────


class TestPathInAllowed:
    def test_exact_match(self):
        assert _path_in_allowed("src/foo.py", ["src/foo.py"]) is True

    def test_prefix_match(self):
        assert _path_in_allowed("src/sub/bar.py", ["src/"]) is True

    def test_no_match(self):
        assert _path_in_allowed("other/bar.py", ["src/"]) is False

    def test_empty_allowed_list(self):
        assert _path_in_allowed("anything.py", []) is False

    def test_backslash_normalised(self):
        assert _path_in_allowed("src\\foo.py", ["src/foo.py"]) is True

    def test_multiple_patterns(self):
        assert _path_in_allowed("docs/readme.md", ["src/", "docs/"]) is True


# ── READ_ASSIGNED ─────────────────────────────────────────────────────────────


class TestReadAssigned:
    def test_allowed_when_no_path_check(self):
        r = check_permission(Action.READ_ASSIGNED, confidence=50)
        assert r.allowed is True

    def test_allowed_when_path_in_list(self):
        r = check_permission(
            Action.READ_ASSIGNED,
            confidence=50,
            allowed_files=["src/"],
            target_path="src/main.py",
        )
        assert r.allowed is True

    def test_denied_when_path_not_in_list(self):
        r = check_permission(
            Action.READ_ASSIGNED,
            confidence=50,
            allowed_files=["src/"],
            target_path="secret/token.txt",
        )
        assert r.allowed is False


# ── READ_UNRELATED ────────────────────────────────────────────────────────────


class TestReadUnrelated:
    def test_always_allowed(self):
        r = check_permission(Action.READ_UNRELATED, confidence=0)
        assert r.allowed is True


# ── EDIT_ASSIGNED ─────────────────────────────────────────────────────────────


class TestEditAssigned:
    def test_allowed_with_sufficient_confidence(self):
        r = check_permission(Action.EDIT_ASSIGNED, confidence=75)
        assert r.allowed is True

    def test_blocked_below_75(self):
        r = check_permission(Action.EDIT_ASSIGNED, confidence=74)
        assert r.allowed is False

    def test_blocked_when_path_outside_allowed(self):
        r = check_permission(
            Action.EDIT_ASSIGNED,
            confidence=90,
            allowed_files=["src/"],
            target_path="external/file.py",
        )
        assert r.allowed is False

    def test_allowed_when_path_matches(self):
        r = check_permission(
            Action.EDIT_ASSIGNED,
            confidence=90,
            allowed_files=["src/"],
            target_path="src/module.py",
        )
        assert r.allowed is True


# ── EDIT_UNASSIGNED ───────────────────────────────────────────────────────────


class TestEditUnassigned:
    def test_always_denied(self):
        r = check_permission(Action.EDIT_UNASSIGNED, confidence=100)
        assert r.allowed is False
        assert "halt" in r.reason.lower()


# ── GIT_COMMIT ────────────────────────────────────────────────────────────────


class TestGitCommit:
    def test_allowed_when_all_conditions_met(self):
        r = check_permission(
            Action.GIT_COMMIT,
            confidence=THRESHOLD_COMMIT,
            verifier_approved=True,
            risk_level="low",
        )
        assert r.allowed is True

    def test_blocked_below_threshold(self):
        r = check_permission(
            Action.GIT_COMMIT,
            confidence=THRESHOLD_COMMIT - 1,
            verifier_approved=True,
        )
        assert r.allowed is False

    def test_blocked_without_verifier(self):
        r = check_permission(
            Action.GIT_COMMIT,
            confidence=99,
            verifier_approved=False,
        )
        assert r.allowed is False

    def test_blocked_at_critical_risk(self):
        r = check_permission(
            Action.GIT_COMMIT,
            confidence=99,
            verifier_approved=True,
            risk_level="critical",
        )
        assert r.allowed is False
        assert r.requires_human is True


# ── GIT_PUSH ──────────────────────────────────────────────────────────────────


class TestGitPush:
    def test_allowed_when_all_conditions_met(self):
        r = check_permission(
            Action.GIT_PUSH,
            confidence=THRESHOLD_PUSH,
            verifier_approved=True,
            tests_passed=True,
            risk_level="low",
        )
        assert r.allowed is True

    def test_blocked_when_commit_denied(self):
        r = check_permission(
            Action.GIT_PUSH,
            confidence=0,
            verifier_approved=False,
        )
        assert r.allowed is False

    def test_blocked_without_tests(self):
        r = check_permission(
            Action.GIT_PUSH,
            confidence=THRESHOLD_PUSH,
            verifier_approved=True,
            tests_passed=False,
            risk_level="low",
        )
        assert r.allowed is False

    def test_blocked_at_high_risk(self):
        r = check_permission(
            Action.GIT_PUSH,
            confidence=THRESHOLD_PUSH,
            verifier_approved=True,
            tests_passed=True,
            risk_level="high",
        )
        assert r.allowed is False
        assert r.requires_human is True


# ── GIT_PR_REVIEW ─────────────────────────────────────────────────────────────


class TestGitPRReview:
    def test_allowed_when_push_allowed(self):
        r = check_permission(
            Action.GIT_PR_REVIEW,
            confidence=THRESHOLD_PUSH,
            verifier_approved=True,
            tests_passed=True,
            risk_level="low",
        )
        assert r.allowed is True

    def test_blocked_when_push_denied(self):
        r = check_permission(
            Action.GIT_PR_REVIEW,
            confidence=0,
            verifier_approved=False,
        )
        assert r.allowed is False


# ── GIT_MERGE ─────────────────────────────────────────────────────────────────


class TestGitMerge:
    def test_allowed_when_all_conditions_met(self):
        r = check_permission(
            Action.GIT_MERGE,
            confidence=THRESHOLD_MERGE,
            verifier_approved=True,
            tests_passed=True,
            ci_passed=True,
            risk_level="low",
        )
        assert r.allowed is True

    def test_blocked_without_ci(self):
        r = check_permission(
            Action.GIT_MERGE,
            confidence=THRESHOLD_MERGE,
            verifier_approved=True,
            tests_passed=True,
            ci_passed=False,
            risk_level="low",
        )
        assert r.allowed is False

    def test_blocked_below_threshold(self):
        r = check_permission(
            Action.GIT_MERGE,
            confidence=THRESHOLD_MERGE - 1,
            verifier_approved=True,
            tests_passed=True,
            ci_passed=True,
            risk_level="low",
        )
        assert r.allowed is False
        assert r.requires_human is True

    def test_blocked_at_medium_risk(self):
        r = check_permission(
            Action.GIT_MERGE,
            confidence=THRESHOLD_MERGE,
            verifier_approved=True,
            tests_passed=True,
            ci_passed=True,
            risk_level="medium",
        )
        assert r.allowed is False


# ── Hardcoded-block actions ───────────────────────────────────────────────────


class TestHardBlockedActions:
    @pytest.mark.parametrize(
        "action",
        [Action.DELETE, Action.RENAME_MAJOR, Action.CHANGE_CONFIG, Action.INSTALL_PACKAGES],
    )
    def test_requires_human(self, action):
        r = check_permission(action, confidence=100)
        assert r.allowed is False
        assert r.requires_human is True

    def test_touch_secrets_denied(self):
        r = check_permission(Action.TOUCH_SECRETS, confidence=100)
        assert r.allowed is False
        assert "halt" in r.reason.lower()


# ── RUN_TESTS ─────────────────────────────────────────────────────────────────


class TestRunTests:
    def test_always_allowed(self):
        r = check_permission(Action.RUN_TESTS, confidence=0)
        assert r.allowed is True


# ── PUSH_MERGE_DEPLOY ─────────────────────────────────────────────────────────


class TestPushMergeDeploy:
    def test_allowed_when_push_ok(self):
        r = check_permission(
            Action.PUSH_MERGE_DEPLOY,
            confidence=THRESHOLD_PUSH,
            verifier_approved=True,
            tests_passed=True,
            risk_level="low",
        )
        assert r.allowed is True

    def test_blocked_when_push_denied(self):
        r = check_permission(
            Action.PUSH_MERGE_DEPLOY,
            confidence=0,
            verifier_approved=False,
        )
        assert r.allowed is False
        assert r.requires_human is True


# ── PermissionResult dataclass ────────────────────────────────────────────────


class TestPermissionResult:
    def test_defaults(self):
        pr = PermissionResult(allowed=True, reason="ok")
        assert pr.requires_human is False

    def test_explicit_requires_human(self):
        pr = PermissionResult(allowed=False, reason="blocked", requires_human=True)
        assert pr.requires_human is True
