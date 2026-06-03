"""Tests for ChromaticRouter: routing decisions, gate blocking, fallback, adapter execution."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from router.router import ChromaticRouter
from router.contracts import (
    RouteRequest,
    RouteResponse,
    RouteInput,
    RouteConstraints,
    RouteConfidence,
    RouteAudit,
    RouteOutput,
    OutputType,
    TaskType,
    PrivacyClass,
    ConfidenceBand,
)
from router.adapters.base import BaseAdapter, AdapterHealth
from router.confidence import ConfidenceGate


# ── Fake adapter for testing ──────────────────────────────────────────────────

class FakeAdapter(BaseAdapter):
    def __init__(self, name: str, *, mode: str = "ok", enabled: bool = True):
        super().__init__(name, {"enabled": enabled})
        self.mode = mode
        self.calls: list[RouteRequest] = []

    async def complete(self, req: RouteRequest) -> RouteResponse:
        self.calls.append(req)
        if self.mode == "raise":
            raise RuntimeError(f"{self.name} failed")
        if self.mode == "error":
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.ERROR, content="adapter error"),
            )
        return RouteResponse(
            request_id=req.request_id,
            selected_provider=self.name,
            output=RouteOutput(type=OutputType.TEXT, content=f"ok from {self.name}"),
        )

    async def health(self) -> AdapterHealth:
        return AdapterHealth(reachable=True, latency_ms=1)


# ── Helper factories ──────────────────────────────────────────────────────────

def _make_req(
    privacy_class: PrivacyClass = PrivacyClass.P1,
    confidence_score: float = 80.0,
    preferred_provider: str = "mock",
    task_type: TaskType = TaskType.CLASSIFICATION,
    objective: str = "test objective",
    max_cost_usd: float = 1.0,
    allow_openhuman: bool = False,
    fallback_chain: list[str] | None = None,
    human_gate_required: bool = False,
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id="r-test",
        task_id="t-test",
        task_type=task_type,
        objective=objective,
        input=RouteInput(messages=messages or []),
        constraints=RouteConstraints(
            privacy_class=privacy_class,
            max_cost_usd=max_cost_usd,
            allow_openhuman=allow_openhuman,
        ),
        confidence=RouteConfidence(
            score=confidence_score,
            band=ConfidenceGate.band_from_score(confidence_score),
        ),
        preferred_provider=preferred_provider,
        fallback_chain=fallback_chain or [],
        audit=RouteAudit(caller="test", human_gate_required=human_gate_required),
    )


def _router_with_mock() -> ChromaticRouter:
    mock = FakeAdapter("mock", mode="ok")
    return ChromaticRouter(adapters={"mock": mock})


# ── Basic routing ─────────────────────────────────────────────────────────────

class TestBasicRouting:
    @pytest.mark.asyncio
    async def test_route_returns_response(self):
        router = _router_with_mock()
        req = _make_req()
        resp = await router.route(req)
        assert isinstance(resp, RouteResponse)

    @pytest.mark.asyncio
    async def test_request_id_preserved(self):
        router = _router_with_mock()
        req = _make_req()
        resp = await router.route(req)
        assert resp.request_id == req.request_id

    @pytest.mark.asyncio
    async def test_mock_provider_selected_when_preferred(self):
        router = _router_with_mock()
        req = _make_req(preferred_provider="mock")
        resp = await router.route(req)
        assert resp.selected_provider == "mock"
        assert resp.output.type == OutputType.TEXT

    @pytest.mark.asyncio
    async def test_confidence_score_in_response(self):
        router = _router_with_mock()
        req = _make_req(confidence_score=85.0)
        resp = await router.route(req)
        assert resp.confidence_score == 85.0

    @pytest.mark.asyncio
    async def test_privacy_class_in_response(self):
        router = _router_with_mock()
        req = _make_req(privacy_class=PrivacyClass.P1)
        resp = await router.route(req)
        assert resp.privacy_class == PrivacyClass.P1

    @pytest.mark.asyncio
    async def test_latency_ms_set(self):
        router = _router_with_mock()
        req = _make_req()
        resp = await router.route(req)
        assert resp.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_logs_populated(self):
        router = _router_with_mock()
        req = _make_req()
        resp = await router.route(req)
        assert isinstance(resp.logs.policy_checks, list)
        assert isinstance(resp.logs.warnings, list)
        assert isinstance(resp.logs.errors, list)


# ── Privacy gate blocking ─────────────────────────────────────────────────────

class TestPrivacyGateBlocking:
    @pytest.mark.asyncio
    async def test_p3_blocked(self):
        router = _router_with_mock()
        req = _make_req(privacy_class=PrivacyClass.P3, confidence_score=95.0)
        resp = await router.route(req)
        assert resp.selected_provider == ""
        assert resp.route_reason == "privacy_gate_blocked"

    @pytest.mark.asyncio
    async def test_p3_error_logged(self):
        router = _router_with_mock()
        req = _make_req(privacy_class=PrivacyClass.P3, confidence_score=95.0)
        resp = await router.route(req)
        assert any("P3" in e for e in resp.logs.errors)

    @pytest.mark.asyncio
    async def test_p4_blocked_without_human_gate(self):
        router = _router_with_mock()
        req = _make_req(
            privacy_class=PrivacyClass.P4,
            confidence_score=95.0,
            human_gate_required=False,
        )
        resp = await router.route(req)
        assert resp.route_reason == "privacy_gate_blocked"

    @pytest.mark.asyncio
    async def test_p4_allowed_with_human_gate(self):
        router = _router_with_mock()
        req = _make_req(
            privacy_class=PrivacyClass.P4,
            confidence_score=95.0,
            human_gate_required=True,
        )
        resp = await router.route(req)
        # Should not be blocked by privacy gate (may pass or hit other gates)
        assert resp.route_reason != "privacy_gate_blocked"

    @pytest.mark.asyncio
    async def test_p1_not_blocked_by_privacy(self):
        router = _router_with_mock()
        req = _make_req(privacy_class=PrivacyClass.P1, confidence_score=80.0)
        resp = await router.route(req)
        assert resp.route_reason != "privacy_gate_blocked"


# ── Confidence gate blocking ───────────────────────────────────────────────────

class TestConfidenceGateBlocking:
    @pytest.mark.asyncio
    async def test_below_60_blocked(self):
        router = _router_with_mock()
        req = _make_req(confidence_score=45.0)
        resp = await router.route(req)
        assert resp.selected_provider == ""
        assert resp.route_reason == "confidence_gate_blocked"
        assert any("60" in e for e in resp.logs.errors)

    @pytest.mark.asyncio
    async def test_at_60_allowed(self):
        router = _router_with_mock()
        req = _make_req(confidence_score=60.0)
        resp = await router.route(req)
        assert resp.route_reason != "confidence_gate_blocked"

    @pytest.mark.asyncio
    async def test_at_100_allowed(self):
        router = _router_with_mock()
        req = _make_req(confidence_score=100.0)
        resp = await router.route(req)
        assert resp.route_reason != "confidence_gate_blocked"

    @pytest.mark.asyncio
    async def test_zero_blocked(self):
        router = _router_with_mock()
        req = _make_req(confidence_score=0.0)
        resp = await router.route(req)
        assert resp.route_reason == "confidence_gate_blocked"


# ── Fallback logic ────────────────────────────────────────────────────────────

class TestFallbackLogic:
    @pytest.mark.asyncio
    async def test_falls_through_to_fallback_on_error_response(self):
        broken = FakeAdapter("primary", mode="error")
        good = FakeAdapter("mock", mode="ok")
        router = ChromaticRouter(adapters={"primary": broken, "mock": good})
        req = _make_req(preferred_provider="primary", fallback_chain=["mock"])
        resp = await router.route(req)
        assert resp.selected_provider == "mock"
        assert resp.output.type == OutputType.TEXT

    @pytest.mark.asyncio
    async def test_falls_through_to_fallback_on_exception(self):
        boom = FakeAdapter("primary", mode="raise")
        good = FakeAdapter("mock", mode="ok")
        router = ChromaticRouter(adapters={"primary": boom, "mock": good})
        req = _make_req(preferred_provider="primary", fallback_chain=["mock"])
        resp = await router.route(req)
        assert resp.selected_provider == "mock"

    @pytest.mark.asyncio
    async def test_fallback_used_flag_set(self):
        good_mock = FakeAdapter("mock", mode="ok")
        router = ChromaticRouter(adapters={"mock": good_mock})
        # openhuman not in adapters → skip → fall through to mock
        req = _make_req(
            preferred_provider="openhuman",
            allow_openhuman=True,
            confidence_score=90.0,
            privacy_class=PrivacyClass.P1,
        )
        resp = await router.route(req)
        assert resp.selected_provider == "mock"
        assert resp.fallback_used is True

    @pytest.mark.asyncio
    async def test_all_fail_returns_error(self):
        a = FakeAdapter("p1", mode="error")
        b = FakeAdapter("p2", mode="raise")
        router = ChromaticRouter(adapters={"p1": a, "p2": b})
        req = _make_req(preferred_provider="p1", fallback_chain=["p2"])
        resp = await router.route(req)
        assert resp.output.type == OutputType.ERROR

    @pytest.mark.asyncio
    async def test_disabled_adapter_skipped(self):
        disabled = FakeAdapter("primary", mode="ok", enabled=False)
        good = FakeAdapter("mock", mode="ok")
        router = ChromaticRouter(adapters={"primary": disabled, "mock": good})
        req = _make_req(preferred_provider="primary", fallback_chain=["mock"])
        resp = await router.route(req)
        assert resp.selected_provider == "mock"


# ── Adapter alias resolution ───────────────────────────────────────────────────

class TestAdapterAliasResolution:
    def test_ollama_local_resolves_to_ollama(self):
        router = _router_with_mock()
        assert router._resolve_adapter_name("ollama_local") == "ollama"

    def test_ollama_remote_desktop_resolves_to_ollama(self):
        router = _router_with_mock()
        assert router._resolve_adapter_name("ollama_remote_desktop") == "ollama"

    def test_unknown_name_returns_itself(self):
        router = _router_with_mock()
        assert router._resolve_adapter_name("some_custom") == "some_custom"

    def test_registered_name_returns_itself(self):
        router = _router_with_mock()
        assert router._resolve_adapter_name("mock") == "mock"

    @pytest.mark.asyncio
    async def test_ollama_local_routes_through_ollama_adapter(self):
        ollama = FakeAdapter("ollama", mode="ok")
        router = ChromaticRouter(adapters={"ollama": ollama, "mock": FakeAdapter("mock")})
        req = _make_req(preferred_provider="ollama_local")
        resp = await router.route(req)
        assert resp.output.type == OutputType.TEXT
        assert ollama.calls  # adapter was called


# ── _build_request convenience method ────────────────────────────────────────

class TestBuildRequest:
    @pytest.mark.asyncio
    async def test_build_request_with_kwargs(self):
        router = _router_with_mock()
        resp = await router.route(
            task_type="classification",
            objective="test via kwargs",
            privacy_class="P1",
            confidence_score=80.0,
            preferred_provider="mock",
        )
        assert resp.request_id
        assert resp.selected_provider == "mock"

    @pytest.mark.asyncio
    async def test_build_request_generates_uuid(self):
        router = _router_with_mock()
        resp1 = await router.route(
            task_type="classification",
            objective="task 1",
            confidence_score=80.0,
            preferred_provider="mock",
        )
        resp2 = await router.route(
            task_type="classification",
            objective="task 2",
            confidence_score=80.0,
            preferred_provider="mock",
        )
        assert resp1.request_id != resp2.request_id


# ── Request prompt text extraction ───────────────────────────────────────────

class TestRequestPromptText:
    def test_extracts_string_content_messages(self):
        req = _make_req(messages=[
            {"role": "user", "content": "hello world"},
            {"role": "assistant", "content": "hi there"},
        ])
        text = ChromaticRouter._request_prompt_text(req)
        assert "hello world" in text
        assert "hi there" in text

    def test_extracts_list_content_messages(self):
        req = _make_req(messages=[
            {"role": "user", "content": [{"type": "text", "text": "nested content"}]},
        ])
        text = ChromaticRouter._request_prompt_text(req)
        assert "nested content" in text

    def test_extracts_metadata_prompt(self):
        req = _make_req()
        req.input.metadata = {"prompt": "metadata prompt text"}
        text = ChromaticRouter._request_prompt_text(req)
        assert "metadata prompt text" in text

    def test_empty_messages_returns_empty(self):
        req = _make_req()
        text = ChromaticRouter._request_prompt_text(req)
        assert text == ""

    def test_ignores_empty_content(self):
        req = _make_req(messages=[
            {"role": "user", "content": ""},
            {"role": "user", "content": "real content"},
        ])
        text = ChromaticRouter._request_prompt_text(req)
        assert text == "real content"


# ── Provider availability ─────────────────────────────────────────────────────

class TestProviderAvailability:
    def test_mock_available(self):
        router = _router_with_mock()
        assert router._provider_is_available("mock") is True

    def test_unregistered_provider_not_available(self):
        router = _router_with_mock()
        assert router._provider_is_available("nonexistent") is False

    def test_disabled_adapter_not_available(self):
        adapter = FakeAdapter("disabled_p", mode="ok", enabled=False)
        router = ChromaticRouter(adapters={"disabled_p": adapter})
        assert router._provider_is_available("disabled_p") is False

    def test_openhuman_blocked_without_env_var(self, monkeypatch):
        monkeypatch.delenv("OPENHUMAN_ENABLED", raising=False)
        adapter = FakeAdapter("openhuman", mode="ok")
        router = ChromaticRouter(adapters={"openhuman": adapter, "mock": FakeAdapter("mock")})
        assert router._provider_is_available("openhuman") is False

    def test_openhuman_available_with_env_var(self, monkeypatch):
        monkeypatch.setenv("OPENHUMAN_ENABLED", "true")
        adapter = FakeAdapter("openhuman", mode="ok")
        router = ChromaticRouter(adapters={"openhuman": adapter, "mock": FakeAdapter("mock")})
        req = _make_req(allow_openhuman=True, privacy_class=PrivacyClass.P1)
        assert router._provider_is_available("openhuman", req) is True
