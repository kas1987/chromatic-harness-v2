"""Tests for ContextGate."""

import pytest

from router.context_gate import ContextGate
from router.context_manifest import ContextResourceManifest
from router.contracts import (
    PrivacyClass,
    RouteConstraints,
    RouteRequest,
    TaskType,
)


class TestContextGate:
    @pytest.fixture
    def gate(self):
        return ContextGate()

    @pytest.fixture
    def req(self):
        """A default request with generous constraints."""
        return RouteRequest(
            request_id="test-1",
            task_id="task-1",
            task_type=TaskType.CODING,
            objective="write a parser",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
                max_context_resources=20,
                max_tokens=128_000,
            ),
        )

    def test_happy_path(self, gate, req):
        result = gate.check(req, complexity_level="C3")
        assert result.ok is True
        assert len(result.allowed_resources) > 0
        assert result.estimated_context_tokens > 0
        assert any("allowed" in log for log in result.logs)

    def test_allow_tools_false_blocks_tools(self, gate):
        req = RouteRequest(
            request_id="t2",
            task_id="task-2",
            task_type=TaskType.CODING,
            objective="test",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=False,
                allow_skills=True,
                allow_mcp=True,
                max_tokens=128_000,
            ),
        )
        result = gate.check(req, complexity_level="C3")
        # Tools like bash, read, write should be denied
        tool_denials = [
            d for d in result.denied_resources if d.reason == "allow_tools=False"
        ]
        assert len(tool_denials) > 0
        # Skills should still be allowed
        assert any(r == "test" for r in result.allowed_resources)

    def test_allow_skills_false_blocks_skills(self, gate):
        req = RouteRequest(
            request_id="t3",
            task_id="task-3",
            task_type=TaskType.CODING,
            objective="test",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=False,
                allow_mcp=True,
                max_tokens=128_000,
            ),
        )
        result = gate.check(req, complexity_level="C3")
        skill_denials = [
            d for d in result.denied_resources if d.reason == "allow_skills=False"
        ]
        assert len(skill_denials) > 0

    def test_allow_mcp_false_blocks_mcp(self, gate):
        req = RouteRequest(
            request_id="t4",
            task_id="task-4",
            task_type=TaskType.CODING,
            objective="test",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=False,
                max_tokens=128_000,
            ),
        )
        result = gate.check(req, complexity_level="C3")
        mcp_denials = [
            d for d in result.denied_resources if d.reason == "allow_mcp=False"
        ]
        assert len(mcp_denials) > 0

    def test_resource_cap(self, gate):
        req = RouteRequest(
            request_id="t5",
            task_id="task-5",
            task_type=TaskType.CODING,
            objective="test",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
                max_context_resources=3,
                max_tokens=128_000,
            ),
        )
        result = gate.check(req, complexity_level="C3")
        assert len(result.allowed_resources) <= 3
        cap_denials = [d for d in result.denied_resources if "Resource cap" in d.reason]
        assert len(cap_denials) >= 1 or len(result.allowed_resources) == 3

    def test_context_budget_exceeded(self, gate):
        req = RouteRequest(
            request_id="t6",
            task_id="task-6",
            task_type=TaskType.CODING,
            objective="test",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
                max_tokens=1_000,  # tiny budget
            ),
        )
        result = gate.check(req, complexity_level="C3")
        # With max_tokens=1000 and 25% budget = 250 tokens, should exceed quickly
        # Actually 25% of 1000 = 250 tokens. Default resources sum to ~5000 tokens.
        # So this SHOULD block.
        assert result.ok is False
        assert result.allowed_resources == []  # blocked = nothing allowed
        assert any("BLOCKED" in log for log in result.logs)

    def test_allowlist_restricts(self, gate):
        req = RouteRequest(
            request_id="t7",
            task_id="task-7",
            task_type=TaskType.CODING,
            objective="test",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
                context_resource_allowlist=["read", "write"],
                max_tokens=128_000,
            ),
        )
        result = gate.check(req, complexity_level="C3")
        assert set(result.allowed_resources) == {"read", "write"}

    def test_privacy_p4_blocks_high_risk(self, gate):
        req = RouteRequest(
            request_id="t8",
            task_id="task-8",
            task_type=TaskType.CODING,
            objective="test",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P4,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
                max_tokens=128_000,
            ),
        )
        result = gate.check(req, complexity_level="C1")
        # P4 default manifest has NO resources tagged with P4 privacy class,
        # so candidates=0. The important thing is that P4 policy is correctly applied.
        assert result.ok is True
        assert "bash" not in result.allowed_resources
        assert len(result.allowed_resources) == 0  # no P4-tagged resources in defaults

    def test_task_type_filtering(self, gate):
        req = RouteRequest(
            request_id="t9",
            task_id="task-9",
            task_type=TaskType.CLASSIFICATION,
            objective="classify",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
                max_tokens=128_000,
            ),
        )
        result = gate.check(req, complexity_level="C1")
        # classification only allows tools, and at most 8 resources
        assert all(
            gate.manifest.get(r).resource_type == "tool"
            for r in result.allowed_resources
        )
        assert len(result.allowed_resources) <= 8

    def test_empty_manifest_returns_ok(self):
        gate = ContextGate(manifest=ContextResourceManifest())
        req = RouteRequest(
            request_id="t10",
            task_id="task-10",
            task_type=TaskType.CODING,
            objective="test",
        )
        result = gate.check(req, complexity_level="C1")
        assert result.ok is True
        assert result.allowed_resources == []
        assert result.estimated_context_tokens == 0
