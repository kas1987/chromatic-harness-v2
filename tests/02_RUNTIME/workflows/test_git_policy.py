"""Tests for workflows.git_policy — confidence thresholds and pipeline evaluation."""

from __future__ import annotations

import pytest

from workflows.git_policy import (
    BLOCKED_RISK_FOR_MERGE,
    BLOCKED_RISK_FOR_PUSH,
    THRESHOLD_COMMIT,
    THRESHOLD_MERGE,
    THRESHOLD_PR_REVIEW,
    THRESHOLD_PUSH,
    GitOperation,
    GitPipelineDecision,
    evaluate_git_pipeline,
)


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_threshold_ordering(self):
        assert THRESHOLD_COMMIT < THRESHOLD_PUSH
        assert THRESHOLD_PUSH > THRESHOLD_PR_REVIEW  # push > PR-review
        assert THRESHOLD_MERGE > THRESHOLD_PR_REVIEW

    def test_blocked_risk_for_push_contains_high_and_critical(self):
        assert "high" in BLOCKED_RISK_FOR_PUSH
        assert "critical" in BLOCKED_RISK_FOR_PUSH

    def test_blocked_risk_for_merge_is_superset_of_push(self):
        assert BLOCKED_RISK_FOR_PUSH.issubset(BLOCKED_RISK_FOR_MERGE)

    def test_blocked_risk_for_merge_contains_medium(self):
        assert "medium" in BLOCKED_RISK_FOR_MERGE

    def test_git_operation_values(self):
        values = {op.value for op in GitOperation}
        assert values == {"commit", "push", "open_pr", "merge"}


# ── GitPipelineDecision.to_dict ───────────────────────────────────────────────


class TestGitPipelineDecisionToDict:
    def _make(self, **kwargs) -> GitPipelineDecision:
        defaults = dict(commit=True, push=False, open_pr=False, merge=False, reasons={})
        defaults.update(kwargs)
        return GitPipelineDecision(**defaults)

    def test_to_dict_keys(self):
        d = self._make().to_dict()
        assert {"commit", "push", "open_pr", "merge", "reasons", "thresholds"} <= set(d)

    def test_to_dict_thresholds_present(self):
        d = self._make().to_dict()
        assert "commit" in d["thresholds"]
        assert "merge" in d["thresholds"]

    def test_to_dict_reflects_values(self):
        d = self._make(commit=True, push=True, open_pr=False, merge=False).to_dict()
        assert d["commit"] is True
        assert d["push"] is True
        assert d["open_pr"] is False


# ── All-pass scenario ─────────────────────────────────────────────────────────


class TestAllPassScenario:
    @pytest.fixture
    def decision(self):
        return evaluate_git_pipeline(
            confidence=96,
            risk_level="low",
            verifier_approved=True,
            tests_passed=True,
            ci_passed=True,
            has_staged_changes=True,
            on_protected_branch=False,
            secrets_detected=False,
        )

    def test_commit_allowed(self, decision):
        assert decision.commit is True

    def test_push_allowed(self, decision):
        assert decision.push is True

    def test_open_pr_allowed(self, decision):
        assert decision.open_pr is True

    def test_merge_allowed(self, decision):
        assert decision.merge is True

    def test_all_reasons_allowed(self, decision):
        for v in decision.reasons.values():
            assert v == "allowed"


# ── Secrets block everything ──────────────────────────────────────────────────


class TestSecretsDetected:
    def test_all_blocked_when_secrets(self):
        d = evaluate_git_pipeline(
            confidence=99,
            verifier_approved=True,
            tests_passed=True,
            ci_passed=True,
            secrets_detected=True,
        )
        assert d.commit is False
        assert d.push is False
        assert d.open_pr is False
        assert d.merge is False

    def test_all_reasons_mention_secrets(self):
        d = evaluate_git_pipeline(confidence=99, secrets_detected=True)
        for v in d.reasons.values():
            assert "secret" in v.lower()


# ── Commit gate ───────────────────────────────────────────────────────────────


class TestCommitGate:
    def test_low_confidence_blocks_commit(self):
        d = evaluate_git_pipeline(
            confidence=THRESHOLD_COMMIT - 1,
            verifier_approved=True,
            has_staged_changes=True,
        )
        assert d.commit is False

    def test_exact_threshold_allows_commit(self):
        d = evaluate_git_pipeline(
            confidence=THRESHOLD_COMMIT,
            verifier_approved=True,
            has_staged_changes=True,
            risk_level="low",
        )
        assert d.commit is True

    def test_no_verifier_blocks_commit(self):
        d = evaluate_git_pipeline(
            confidence=99,
            verifier_approved=False,
            has_staged_changes=True,
        )
        assert d.commit is False

    def test_no_staged_changes_blocks_commit(self):
        d = evaluate_git_pipeline(
            confidence=99,
            verifier_approved=True,
            has_staged_changes=False,
        )
        assert d.commit is False

    def test_critical_risk_blocks_commit(self):
        d = evaluate_git_pipeline(
            confidence=99,
            verifier_approved=True,
            has_staged_changes=True,
            risk_level="critical",
        )
        assert d.commit is False


# ── Push gate ─────────────────────────────────────────────────────────────────


class TestPushGate:
    def _base_ok(self, **kwargs):
        params = dict(
            confidence=THRESHOLD_PUSH,
            verifier_approved=True,
            tests_passed=True,
            has_staged_changes=True,
            risk_level="low",
        )
        params.update(kwargs)
        return evaluate_git_pipeline(**params)

    def test_push_allowed_at_threshold(self):
        assert self._base_ok().push is True

    def test_push_blocked_without_tests(self):
        assert self._base_ok(tests_passed=False).push is False

    def test_push_blocked_at_high_risk(self):
        assert self._base_ok(risk_level="high").push is False

    def test_push_blocked_at_critical_risk(self):
        assert self._base_ok(risk_level="critical").push is False

    def test_push_allowed_at_medium_risk(self):
        assert self._base_ok(risk_level="medium").push is True

    def test_push_blocked_below_push_threshold(self):
        assert self._base_ok(confidence=THRESHOLD_PUSH - 1).push is False


# ── Open-PR gate ──────────────────────────────────────────────────────────────


class TestOpenPRGate:
    def _base_ok(self, **kwargs):
        params = dict(
            confidence=THRESHOLD_PUSH,
            verifier_approved=True,
            tests_passed=True,
            has_staged_changes=True,
            risk_level="low",
            on_protected_branch=False,
        )
        params.update(kwargs)
        return evaluate_git_pipeline(**params)

    def test_open_pr_allowed(self):
        assert self._base_ok().open_pr is True

    def test_open_pr_blocked_on_protected_branch(self):
        assert self._base_ok(on_protected_branch=True).open_pr is False


# ── Merge gate ────────────────────────────────────────────────────────────────


class TestMergeGate:
    def _base_ok(self, **kwargs):
        params = dict(
            confidence=THRESHOLD_MERGE,
            verifier_approved=True,
            tests_passed=True,
            ci_passed=True,
            has_staged_changes=True,
            risk_level="low",
            on_protected_branch=False,
        )
        params.update(kwargs)
        return evaluate_git_pipeline(**params)

    def test_merge_allowed(self):
        assert self._base_ok().merge is True

    def test_merge_blocked_without_ci(self):
        assert self._base_ok(ci_passed=False).merge is False

    def test_merge_blocked_at_medium_risk(self):
        assert self._base_ok(risk_level="medium").merge is False

    def test_merge_blocked_below_threshold(self):
        assert self._base_ok(confidence=THRESHOLD_MERGE - 1).merge is False


# ── Cascading denial ─────────────────────────────────────────────────────────


class TestCascadingDenial:
    def test_commit_fail_cascades_to_all(self):
        d = evaluate_git_pipeline(
            confidence=0,
            verifier_approved=False,
            tests_passed=True,
            ci_passed=True,
            has_staged_changes=True,
        )
        assert d.commit is False
        assert d.push is False
        assert d.open_pr is False
        assert d.merge is False
