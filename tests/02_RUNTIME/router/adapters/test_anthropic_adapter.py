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


# ---------------------------------------------------------------------------
# complete() — prompt caching + system message extraction
# ---------------------------------------------------------------------------


def _fake_response_with_cache(
    content: str = "ok",
    input_tokens: int = 10,
    output_tokens: int = 5,
    cache_read: int = 0,
    cache_write: int = 0,
):
    """Fake response that includes Anthropic cache token fields."""
    from types import SimpleNamespace
    usage = SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_write,
    )
    return SimpleNamespace(content=[SimpleNamespace(text=content)], usage=usage)


@pytest.mark.asyncio
class TestAnthropicAdapterCaching:
    def _adapter(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            return AnthropicAdapter()

    async def test_system_message_sent_via_system_param(self):
        """role=system is extracted and sent via system=, not in messages=."""
        adapter = self._adapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=_fake_response_with_cache())
        adapter._client = mock_client

        msgs = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "hello"},
        ]
        await adapter.complete(_make_request(messages=msgs))

        kwargs = mock_client.messages.create.call_args.kwargs
        assert "system" in kwargs
        assert kwargs["system"][0]["text"] == "Be concise."
        assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}

    async def test_system_message_removed_from_messages_list(self):
        """role=system must not appear inside messages= (Anthropic rejects it)."""
        adapter = self._adapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=_fake_response_with_cache())
        adapter._client = mock_client

        msgs = [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": "user turn"},
        ]
        await adapter.complete(_make_request(messages=msgs))

        kwargs = mock_client.messages.create.call_args.kwargs
        for m in kwargs["messages"]:
            assert m.get("role") != "system"

    async def test_system_message_mid_list_also_extracted(self):
        """System messages are filtered regardless of position."""
        adapter = self._adapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=_fake_response_with_cache())
        adapter._client = mock_client

        msgs = [
            {"role": "user", "content": "first"},
            {"role": "system", "content": "Late system msg."},
            {"role": "user", "content": "second"},
        ]
        await adapter.complete(_make_request(messages=msgs))

        kwargs = mock_client.messages.create.call_args.kwargs
        assert "system" in kwargs
        for m in kwargs["messages"]:
            assert m.get("role") != "system"

    async def test_system_content_as_list_of_blocks(self):
        """system content as list-of-blocks is joined into a string."""
        adapter = self._adapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=_fake_response_with_cache())
        adapter._client = mock_client

        msgs = [
            {"role": "system", "content": [
                {"type": "text", "text": "Part one."},
                {"type": "text", "text": "Part two."},
            ]},
            {"role": "user", "content": "hi"},
        ]
        await adapter.complete(_make_request(messages=msgs))

        kwargs = mock_client.messages.create.call_args.kwargs
        assert "Part one." in kwargs["system"][0]["text"]
        assert "Part two." in kwargs["system"][0]["text"]

    async def test_empty_chat_messages_falls_back_to_objective(self):
        """If only system messages are present, fall back to req.objective."""
        adapter = self._adapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=_fake_response_with_cache())
        adapter._client = mock_client

        msgs = [{"role": "system", "content": "Only a system prompt."}]
        await adapter.complete(_make_request(objective="fallback objective", messages=msgs))

        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["messages"] == [{"role": "user", "content": "fallback objective"}]

    async def test_cache_tokens_reported_in_usage(self):
        """cache_read_tokens and cache_write_tokens surface in RouteUsage."""
        adapter = self._adapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            return_value=_fake_response_with_cache(cache_read=120, cache_write=300)
        )
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.usage.cache_read_tokens == 120
        assert resp.usage.cache_write_tokens == 300

    async def test_no_system_message_no_system_param(self):
        """Without a system message, system= is not added to the API call."""
        adapter = self._adapter()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=_fake_response_with_cache())
        adapter._client = mock_client

        await adapter.complete(_make_request(messages=[{"role": "user", "content": "hello"}]))

        kwargs = mock_client.messages.create.call_args.kwargs
        assert "system" not in kwargs
