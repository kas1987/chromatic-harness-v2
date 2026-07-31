"""Unit tests for the OmniRoute adapter (bead chromatic-harness-v2-wisp-2yz.1)."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from router.adapters.omniroute_adapter import OmniRouteAdapter
from router.contracts import (
    ConfidenceBand,
    RouteConfidence,
    RouteConstraints,
    RouteInput,
    RouteRequest,
    RouteResponse,
    TaskType,
)


# ── Construction / configuration ─────────────────────────────────────────────


def test_adapter_defaults():
    adapter = OmniRouteAdapter({})
    assert adapter.name == "omniroute"
    assert adapter.enabled is True
    assert adapter.cfg["base_url"] == "http://localhost:20128/v1"
    assert adapter.cfg["model"] == "oc/deepseek-v4-flash-free"


def test_adapter_disabled_without_base_url():
    adapter = OmniRouteAdapter({"base_url": "", "enabled": True})
    assert adapter.enabled is False


def test_adapter_respects_explicit_base_url_and_model():
    adapter = OmniRouteAdapter({"base_url": "http://127.0.0.1:9999/v1", "model": "auto/coding"})
    assert adapter.cfg["base_url"] == "http://127.0.0.1:9999/v1"
    assert adapter.cfg["model"] == "auto/coding"


def test_api_key_uses_env_then_dummy(monkeypatch):
    adapter = OmniRouteAdapter({})
    assert adapter._api_key() == "not-needed"

    monkeypatch.setenv("OMNIROUTE_API_KEY", "sk_real")
    assert adapter._api_key() == "sk_real"


# ── health() ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_reachable(monkeypatch):
    adapter = OmniRouteAdapter({})

    async def fake_get(url: str, **kwargs: Any) -> httpx.Response:
        assert url == "http://localhost:20128/v1/models"
        return httpx.Response(200, json={"data": []})

    fake_client = httpx.AsyncClient()
    fake_client.get = fake_get  # type: ignore[method-assign]
    monkeypatch.setattr(adapter, "_get_client", lambda: fake_client)

    health = await adapter.health()
    assert health.reachable is True
    assert health.latency_ms >= 0


@pytest.mark.asyncio
async def test_health_unreachable(monkeypatch):
    adapter = OmniRouteAdapter({})

    async def fake_get(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway")

    fake_client = httpx.AsyncClient()
    fake_client.get = fake_get  # type: ignore[method-assign]
    monkeypatch.setattr(adapter, "_get_client", lambda: fake_client)

    health = await adapter.health()
    assert health.reachable is False


@pytest.mark.asyncio
async def test_health_disabled():
    adapter = OmniRouteAdapter({"base_url": "", "enabled": True})
    health = await adapter.health()
    assert health.reachable is False
    assert "disabled" in health.error


# ── complete() ───────────────────────────────────────────────────────────────


def _make_request() -> RouteRequest:
    return RouteRequest(
        request_id="req-1",
        task_id="task-1",
        task_type=TaskType.CODING,
        objective="Say hello",
        input=RouteInput(messages=[{"role": "user", "content": "Say hello"}]),
        constraints=RouteConstraints(max_tokens=256),
        confidence=RouteConfidence(score=95.0, band=ConfidenceBand.VERY_HIGH, reason="test"),
        preferred_provider="omniroute",
    )


@pytest.mark.asyncio
async def test_complete_success(monkeypatch):
    adapter = OmniRouteAdapter({})

    async def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        assert url == "http://localhost:20128/v1/chat/completions"
        body = kwargs.get("json", {})
        assert body["model"] == "oc/deepseek-v4-flash-free"
        assert body["messages"] == [{"role": "user", "content": "Say hello"}]
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hello!"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            },
        )

    fake_client = httpx.AsyncClient()
    fake_client.post = fake_post  # type: ignore[method-assign]
    monkeypatch.setattr(adapter, "_get_client", lambda: fake_client)

    req = _make_request()
    resp = await adapter.complete(req)
    assert resp.selected_provider == "omniroute"
    assert resp.selected_model == "oc/deepseek-v4-flash-free"
    assert resp.output.content == "Hello!"
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 2
    assert resp.usage.total_tokens == 12


@pytest.mark.asyncio
async def test_complete_error_status(monkeypatch):
    adapter = OmniRouteAdapter({})

    async def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    fake_client = httpx.AsyncClient()
    fake_client.post = fake_post  # type: ignore[method-assign]
    monkeypatch.setattr(adapter, "_get_client", lambda: fake_client)

    req = _make_request()
    resp = await adapter.complete(req)
    assert resp.output.type.value == "error"
    assert "429" in resp.output.content


@pytest.mark.asyncio
async def test_complete_exception(monkeypatch):
    adapter = OmniRouteAdapter({})

    async def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    fake_client = httpx.AsyncClient()
    fake_client.post = fake_post  # type: ignore[method-assign]
    monkeypatch.setattr(adapter, "_get_client", lambda: fake_client)

    req = _make_request()
    resp = await adapter.complete(req)
    assert resp.output.type.value == "error"
    assert "Connection refused" in resp.output.content


@pytest.mark.asyncio
async def test_complete_disabled():
    adapter = OmniRouteAdapter({"base_url": "", "enabled": True})
    req = _make_request()
    resp = await adapter.complete(req)
    assert resp.output.type.value == "error"
    assert "disabled" in resp.output.content
