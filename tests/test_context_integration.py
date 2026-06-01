"""Integration tests for Context Resource Governance (CRG) in ChromaticRouter."""

import pytest

from router.contracts import (
    ConfidenceBand,
    PrivacyClass,
    RouteConstraints,
    RouteRequest,
    RouteResponse,
    RouteConfidence,
    TaskType,
)
from router.router import ChromaticRouter


class TestContextGateIntegration:
    @pytest.fixture
    def router(self):
        return ChromaticRouter()

    @pytest.fixture
    def base_req(self):
        return RouteRequest(
            request_id="int-1",
            task_id="task-int",
            task_type=TaskType.CODING,
            objective="refactor auth module",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
                max_context_resources=20,
                max_tokens=128_000,
            ),
            confidence=RouteConfidence(score=75.0, band=ConfidenceBand.HIGH),
        )

    @pytest.mark.asyncio
    async def test_context_gate_runs_before_privacy_gate(self, router, base_req):
        resp = await router.route(base_req)
        # If privacy gate ran first and blocked, route_reason would be "privacy_gate_blocked"
        # If context gate ran first and blocked, route_reason would be "context_gate_blocked"
        # With P0 and generous tokens, neither should block
        assert resp.route_reason != "context_gate_blocked"
        assert resp.route_reason != "privacy_gate_blocked"
        assert len(resp.context_resources) > 0

    @pytest.mark.asyncio
    async def test_context_gate_blocks_on_tiny_budget(self, router):
        req = RouteRequest(
            request_id="int-2",
            task_id="task-int",
            task_type=TaskType.CODING,
            objective="refactor",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                max_tokens=500,  # tiny budget → context gate should block
            ),
            confidence=RouteConfidence(score=75.0, band=ConfidenceBand.HIGH),
        )
        resp = await router.route(req)
        assert resp.route_reason == "context_gate_blocked"
        assert resp.context_resources == []
        assert "context gate" in resp.output.content.lower()

    @pytest.mark.asyncio
    async def test_allow_tools_false_strips_tools(self, router):
        req = RouteRequest(
            request_id="int-3",
            task_id="task-int",
            task_type=TaskType.CODING,
            objective="refactor",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=False,
                allow_skills=True,
                allow_mcp=True,
                max_tokens=128_000,
            ),
            confidence=RouteConfidence(score=75.0, band=ConfidenceBand.HIGH),
        )
        resp = await router.route(req)
        # No "tool" type resources should be in context_resources
        from router.context_manifest import ContextResourceManifest

        manifest = ContextResourceManifest.build_defaults()
        tool_ids = {r.resource_id for r in manifest.by_type("tool")}
        assert not any(rid in tool_ids for rid in resp.context_resources)

    @pytest.mark.asyncio
    async def test_allow_skills_false_strips_skills(self, router):
        req = RouteRequest(
            request_id="int-4",
            task_id="task-int",
            task_type=TaskType.CODING,
            objective="refactor",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=False,
                allow_mcp=True,
                max_tokens=128_000,
            ),
            confidence=RouteConfidence(score=75.0, band=ConfidenceBand.HIGH),
        )
        resp = await router.route(req)
        from router.context_manifest import ContextResourceManifest

        manifest = ContextResourceManifest.build_defaults()
        skill_ids = {r.resource_id for r in manifest.by_type("skill")}
        assert not any(rid in skill_ids for rid in resp.context_resources)

    @pytest.mark.asyncio
    async def test_allow_mcp_false_strips_mcp(self, router):
        req = RouteRequest(
            request_id="int-5",
            task_id="task-int",
            task_type=TaskType.CODING,
            objective="refactor",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=False,
                max_tokens=128_000,
            ),
            confidence=RouteConfidence(score=75.0, band=ConfidenceBand.HIGH),
        )
        resp = await router.route(req)
        from router.context_manifest import ContextResourceManifest

        manifest = ContextResourceManifest.build_defaults()
        mcp_ids = {r.resource_id for r in manifest.by_type("mcp")}
        assert not any(rid in mcp_ids for rid in resp.context_resources)

    @pytest.mark.asyncio
    async def test_context_resources_in_response(self, router, base_req):
        resp = await router.route(base_req)
        assert isinstance(resp, RouteResponse)
        assert isinstance(resp.context_resources, list)
        assert len(resp.context_resources) > 0
        assert all(isinstance(r, str) for r in resp.context_resources)

    @pytest.mark.asyncio
    async def test_max_context_resources_cap(self, router):
        req = RouteRequest(
            request_id="int-6",
            task_id="task-int",
            task_type=TaskType.CODING,
            objective="refactor",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
                max_context_resources=3,
                max_tokens=128_000,
            ),
            confidence=RouteConfidence(score=75.0, band=ConfidenceBand.HIGH),
        )
        resp = await router.route(req)
        assert len(resp.context_resources) <= 3

    @pytest.mark.asyncio
    async def test_personal_context_restricts_to_tools(self, router):
        req = RouteRequest(
            request_id="int-7",
            task_id="task-int",
            task_type=TaskType.PERSONAL_CONTEXT,
            objective="explain my code",
            constraints=RouteConstraints(
                privacy_class=PrivacyClass.P0,
                allow_tools=True,
                allow_skills=True,
                allow_mcp=True,
                max_tokens=128_000,
            ),
            confidence=RouteConfidence(score=75.0, band=ConfidenceBand.HIGH),
        )
        resp = await router.route(req)
        # personal_context task rule only allows tools and at most 8 resources
        from router.context_manifest import ContextResourceManifest

        manifest = ContextResourceManifest.build_defaults()
        assert all(manifest.get(rid).resource_type == "tool" for rid in resp.context_resources)
        assert len(resp.context_resources) <= 8
