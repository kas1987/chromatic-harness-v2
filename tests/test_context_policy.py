"""Tests for ContextPolicyLoader."""

import pytest

from router.context_policy import ContextPolicyLoader
from router.contracts import PrivacyClass, TaskType


class TestContextPolicyLoader:
    @pytest.fixture
    def loader(self):
        return ContextPolicyLoader()

    def test_load_defaults(self, loader):
        defaults = loader.defaults()
        assert "max_context_budget_pct" in defaults
        assert defaults["max_resources"] == 20

    def test_rules_for_task_coding(self, loader):
        rule = loader.rules_for_task(TaskType.CODING)
        assert rule is not None
        assert rule.max_resources == 16
        assert "secrets_read" in rule.blocked_resources
        assert "tool" in rule.allowed_types

    def test_rules_for_task_personal_context(self, loader):
        rule = loader.rules_for_task(TaskType.PERSONAL_CONTEXT)
        assert rule is not None
        assert rule.max_resources == 6
        assert "bash" in rule.blocked_resources
        assert "write" in rule.blocked_resources
        assert "edit" in rule.blocked_resources

    def test_rules_for_complexity_c1(self, loader):
        cap = loader.rules_for_complexity("C1")
        assert cap is not None
        assert cap.max_resources == 8
        assert cap.max_risk == "low"

    def test_rules_for_complexity_c4(self, loader):
        cap = loader.rules_for_complexity("C4")
        assert cap is not None
        assert cap.max_resources == 24
        assert cap.max_risk == "critical"

    def test_rules_for_privacy_p0(self, loader):
        rule = loader.rules_for_privacy(PrivacyClass.P0)
        assert rule is not None
        assert rule.max_risk == "critical"
        assert "secrets_read" not in rule.blocked_resources

    def test_rules_for_privacy_p4(self, loader):
        rule = loader.rules_for_privacy(PrivacyClass.P4)
        assert rule is not None
        assert rule.max_risk == "low"
        assert "bash" in rule.blocked_resources
        assert "codex_team" in rule.blocked_resources

    def test_context_budget_for_privacy(self, loader):
        assert loader.context_budget_for_privacy(PrivacyClass.P0) == 25
        assert loader.context_budget_for_privacy(PrivacyClass.P4) == 5

    def test_resolve_combined_policy(self, loader):
        policy = loader.resolve(TaskType.CODING, "C3", PrivacyClass.P1)
        assert policy.effective_max_resources() == 16  # coding=16, C3=16, global=20 → 16
        assert policy.effective_budget_pct() == 25
        assert policy.effective_max_risk() == "high"  # P1=high, C3=high → high
        assert policy.is_blocked("secrets_read") is True  # blocked by both task and privacy rule
        assert policy.is_blocked("bash") is False  # not blocked for coding
        assert policy.is_type_allowed("tool") is True

    def test_resolve_p4_restrictive(self, loader):
        policy = loader.resolve(TaskType.RESEARCH, "C1", PrivacyClass.P4)
        assert policy.effective_max_resources() == 8  # min of research(12), C1(8), global(20)
        assert policy.effective_max_risk() == "low"  # P4=low, C1=low → low
        assert policy.is_blocked("bash") is True
        assert policy.is_blocked("codex_team") is True
        assert policy.is_type_allowed("agent") is False  # P4 blocks agents

    def test_missing_file_returns_empty(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            loader = ContextPolicyLoader(f"{td}/nonexistent.yaml")
            assert loader.defaults() == {}
            assert loader.rules_for_task(TaskType.CODING) is None
