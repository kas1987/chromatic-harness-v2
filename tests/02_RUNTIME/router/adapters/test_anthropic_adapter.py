"""Unit tests for the AnthropicAdapter."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from router.adapters.anthropic_adapter import AnthropicAdapter
from router.adapters.base import AdapterError
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
    request_id: str = "req-1",
    objective: str = "say hello",
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-1",
        task_type=TaskType.CODING,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _fake_response(content: str = "Hello!", input_tokens: int = 10, output_tokens: int = 5):
    """Build a minimal fake Anthropic SDK response object."""
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    msg = SimpleNamespace(content=[SimpleNamespace(text=content)], usage=usage)
    return msg


# ---------------------------------------------------------------------------
# Construction / configuration
# ---------------------------------------------------------------------------


class TestAnthropicAdapterInit:
    def test_disabled_when_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = AnthropicAdapter()
        assert adapter.enabled is False
        assert adapter.name == "anthropic"

    def test_enabled_when_api_key_present(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            adapter = AnthropicAdapter()
        assert adapter.enabled is True

    def test_custom_env_key(self):
        with patch.dict(os.environ, {"MY_KEY": "sk-custom"}, clear=True):
            adapter = AnthropicAdapter({"env_key": "MY_KEY"})
        assert adapter.enabled is True

    def test_default_model(self):
        adapter = AnthropicAdapter()
        assert "claude" in adapter.cfg.get("model", "").lower()

    def test_custom_model_preserved(self):
        adapter = AnthropicAdapter({"model": "claude-opus-4-0"})
        assert adapter.cfg["model"] == "claude-opus-4-0"


# ---------------------------------------------------------------------------
# _get_client
# ---------------------------------------------------------------------------


class TestGetClient:
    def test_raises_adapter_error_when_sdk_missing(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            adapter = AnthropicAdapter()
        with patch.dict("sys.modules", {"anthropic": None}):
            with pytest.raises(AdapterError) as exc_info:
                adapter._client = None
                adapter._get_client()
        assert "anthropic" in str(exc_info.value).lower()
        assert exc_info.value.provider == "anthropic"

    def test_returns_cached_client(self):
        adapter = AnthropicAdapter()
        mock_client = MagicMock()
        adapter._client = mock_client
        assert adapter._get_client() is mock_client


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAnthropicAdapterHealth:
    async def test_health_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = AnthropicAdapter()
        health = await adapter.health()
        assert health.reachable is False
        assert "ANTHROPIC_API_KEY" in health.error

    async def test_health_reachable(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.count_tokens = AsyncMock(return_value=None)
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is True
        assert health.latency_ms >= 0
        mock_client.messages.count_tokens.assert_awaited_once()

    async def test_health_exception_returns_unreachable(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.count_tokens = AsyncMock(side_effect=RuntimeError("network error"))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False
        assert "network error" in health.error


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAnthropicAdapterComplete:
    async def test_complete_disabled_returns_error_response(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = AnthropicAdapter()
        req = _make_request()
        resp = await adapter.complete(req)
        assert resp.output.type == OutputType.ERROR
        assert "ANTHROPIC_API_KEY" in resp.output.content

    async def test_complete_success_text_response(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            adapter = AnthropicAdapter()
        fake_resp = _fake_response("Hello from Claude!", input_tokens=15, output_tokens=6)
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_resp)
        adapter._client = mock_client

        req = _make_request(objective="say hello")
        resp = await adapter.complete(req)

        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "Hello from Claude!"
        assert resp.selected_provider == "anthropic"
        assert resp.request_id == "req-1"

    async def test_complete_returns_usage_tokens(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            adapter = AnthropicAdapter()
        fake_resp = _fake_response("Response", input_tokens=20, output_tokens=8)
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_resp)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.usage.input_tokens == 20
        assert resp.usage.output_tokens == 8
        assert resp.usage.total_tokens == 28

    async def test_complete_passes_messages_when_provided(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            adapter = AnthropicAdapter()
        messages = [{"role": "user", "content": "custom message"}]
        fake_resp = _fake_response("ok")
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_resp)
        adapter._client = mock_client

        req = _make_request(messages=messages)
        await adapter.complete(req)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["messages"] == messages

    async def test_complete_falls_back_to_objective_when_no_messages(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            adapter = AnthropicAdapter()
        fake_resp = _fake_response("ok")
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_resp)
        adapter._client = mock_client

        req = _make_request(objective="my objective", messages=[])
        await adapter.complete(req)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["messages"] == [{"role": "user", "content": "my objective"}]

    async def test_complete_exception_returns_error_response(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            adapter = AnthropicAdapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "API down" in resp.output.content

    async def test_complete_records_latency(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            adapter = AnthropicAdapter()
        fake_resp = _fake_response("hi")
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=fake_resp)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.latency_ms >= 0
