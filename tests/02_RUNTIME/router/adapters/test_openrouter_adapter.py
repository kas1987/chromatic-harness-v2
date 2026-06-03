"""Unit tests for the OpenRouterAdapter (httpx-based, OpenAI-compatible)."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from router.adapters.openrouter_adapter import OpenRouterAdapter
from router.contracts import (
    OutputType,
    RouteInput,
    RouteRequest,
    TaskType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    request_id: str = "req-or-1",
    objective: str = "route me",
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-or-1",
        task_type=TaskType.PLANNING,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _mock_httpx_response(
    status_code: int = 200,
    json_body: dict | None = None,
):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {
        "choices": [{"message": {"content": "OpenRouter response"}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
    }
    return resp


# ---------------------------------------------------------------------------
# Construction / auth header injection
# ---------------------------------------------------------------------------


class TestOpenRouterAdapterInit:
    def test_disabled_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = OpenRouterAdapter()
        assert adapter.enabled is False
        assert adapter.name == "openrouter"

    def test_enabled_with_key(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        assert adapter.enabled is True

    def test_auth_header_injected(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
            client = adapter._get_client()
        # httpx masks Authorization header values in .headers repr; use raw headers.
        auth_values = [v for k, v in client.headers.raw if k.lower() == b"authorization"]
        assert auth_values, "Authorization header missing"
        assert b"or-secret" in auth_values[0]

    def test_referer_header_injected(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
            client = adapter._get_client()
        header_names = [k.lower() for k, v in client.headers.raw]
        assert b"http-referer" in header_names

    def test_default_model(self):
        adapter = OpenRouterAdapter()
        assert adapter.cfg.get("model") is not None


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOpenRouterAdapterHealth:
    async def test_health_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = OpenRouterAdapter()
        health = await adapter.health()
        assert health.reachable is False
        assert "OPENROUTER_API_KEY" in health.error

    async def test_health_reachable_200(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        mock_resp = _mock_httpx_response(200)
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is True

    async def test_health_non_200_returns_unreachable(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        mock_resp = _mock_httpx_response(503)
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False

    async def test_health_exception(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False
        assert health.error != ""


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOpenRouterAdapterComplete:
    async def test_complete_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = OpenRouterAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "OPENROUTER_API_KEY" in resp.output.content

    async def test_complete_success(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        mock_resp = _mock_httpx_response(
            200,
            {
                "choices": [{"message": {"content": "Router answer"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
            },
        )
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "Router answer"
        assert resp.selected_provider == "openrouter"

    async def test_complete_http_error_returns_error_response(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        mock_resp = _mock_httpx_response(429)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "429" in resp.output.content

    async def test_complete_500_returns_error_response(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        mock_resp = _mock_httpx_response(500)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "500" in resp.output.content

    async def test_complete_usage_mapping(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        mock_resp = _mock_httpx_response(
            200,
            {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            },
        )
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.usage.input_tokens == 20
        assert resp.usage.output_tokens == 10
        assert resp.usage.total_tokens == 30

    async def test_complete_exception_returns_error(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR

    async def test_complete_messages_passed_through(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        messages = [{"role": "user", "content": "test msg"}]
        mock_resp = _mock_httpx_response(200)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        await adapter.complete(_make_request(messages=messages))
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["messages"] == messages

    async def test_complete_builds_message_from_objective(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-secret"}):
            adapter = OpenRouterAdapter()
        mock_resp = _mock_httpx_response(200)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        await adapter.complete(_make_request(objective="summarize docs", messages=[]))
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["messages"] == [{"role": "user", "content": "summarize docs"}]
