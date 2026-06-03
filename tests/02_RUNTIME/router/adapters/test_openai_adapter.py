"""Unit tests for the OpenAIAdapter."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from router.adapters.base import AdapterError
from router.adapters.openai_adapter import OpenAIAdapter
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
    request_id: str = "req-oai-1",
    objective: str = "translate this",
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-oai-1",
        task_type=TaskType.CODING,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _fake_completion(content: str = "GPT says hi", prompt_tokens: int = 12, completion_tokens: int = 5):
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestOpenAIAdapterInit:
    def test_disabled_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = OpenAIAdapter()
        assert adapter.enabled is False
        assert adapter.name == "openai"

    def test_enabled_with_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-oai-test"}):
            adapter = OpenAIAdapter()
        assert adapter.enabled is True

    def test_default_model_is_gpt(self):
        adapter = OpenAIAdapter()
        assert "gpt" in adapter.cfg.get("model", "").lower()

    def test_custom_model(self):
        adapter = OpenAIAdapter({"model": "gpt-4o"})
        assert adapter.cfg["model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# _get_client
# ---------------------------------------------------------------------------

class TestOpenAIGetClient:
    def test_raises_adapter_error_when_sdk_missing(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = OpenAIAdapter()
        with patch.dict("sys.modules", {"openai": None}):
            adapter._client = None
            with pytest.raises(AdapterError) as exc_info:
                adapter._get_client()
        assert "openai" in str(exc_info.value).lower()
        assert exc_info.value.provider == "openai"

    def test_returns_cached_client(self):
        adapter = OpenAIAdapter()
        sentinel = MagicMock()
        adapter._client = sentinel
        assert adapter._get_client() is sentinel


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOpenAIAdapterHealth:
    async def test_health_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = OpenAIAdapter()
        health = await adapter.health()
        assert health.reachable is False
        assert "OPENAI_API_KEY" in health.error

    async def test_health_reachable(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = OpenAIAdapter()
        mock_models = MagicMock()
        mock_models.list = AsyncMock(return_value=[])
        mock_client = MagicMock()
        mock_client.models = mock_models
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is True
        assert health.latency_ms >= 0

    async def test_health_exception(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = OpenAIAdapter()
        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(side_effect=ConnectionError("timeout"))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False
        assert "timeout" in health.error


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOpenAIAdapterComplete:
    async def test_complete_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = OpenAIAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "OPENAI_API_KEY" in resp.output.content

    async def test_complete_success(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = OpenAIAdapter()
        fake = _fake_completion("Hello from GPT", 10, 4)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "Hello from GPT"
        assert resp.selected_provider == "openai"

    async def test_complete_usage_mapping(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = OpenAIAdapter()
        fake = _fake_completion("ok", prompt_tokens=30, completion_tokens=10)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.usage.input_tokens == 30
        assert resp.usage.output_tokens == 10
        assert resp.usage.total_tokens == 40

    async def test_complete_uses_messages_when_present(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = OpenAIAdapter()
        messages = [{"role": "user", "content": "specific msg"}]
        fake = _fake_completion("ok")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake)
        adapter._client = mock_client

        await adapter.complete(_make_request(messages=messages))
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["messages"] == messages

    async def test_complete_builds_message_from_objective(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = OpenAIAdapter()
        fake = _fake_completion("ok")
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake)
        adapter._client = mock_client

        await adapter.complete(_make_request(objective="my goal", messages=[]))
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["messages"] == [{"role": "user", "content": "my goal"}]

    async def test_complete_exception_returns_error(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = OpenAIAdapter()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("rate limited"))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "rate limited" in resp.output.content

    async def test_complete_latency_recorded(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = OpenAIAdapter()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.latency_ms >= 0

    async def test_complete_request_id_preserved(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            adapter = OpenAIAdapter()
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_fake_completion())
        adapter._client = mock_client

        req = _make_request(request_id="my-special-id")
        resp = await adapter.complete(req)
        assert resp.request_id == "my-special-id"
