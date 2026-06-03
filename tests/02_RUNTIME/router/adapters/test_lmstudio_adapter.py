"""Unit tests for LMStudioAdapter (local inference server)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from router.adapters.lmstudio_adapter import LMStudioAdapter
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
    request_id: str = "req-lms-1",
    objective: str = "write a function",
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-lms-1",
        task_type=TaskType.CODING,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _mock_response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {
        "choices": [{"message": {"content": "LMStudio says hi"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    return resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestLMStudioAdapterInit:
    def test_default_construction(self):
        adapter = LMStudioAdapter()
        assert adapter.name == "lmstudio"
        assert adapter.enabled is True  # local adapter — enabled by default

    def test_default_host_port(self):
        adapter = LMStudioAdapter()
        assert adapter.cfg.get("host") == "localhost"
        assert adapter.cfg.get("port") == 1234

    def test_url_construction(self):
        adapter = LMStudioAdapter()
        url = adapter._url("/v1/chat/completions")
        assert url == "http://localhost:1234/v1/chat/completions"

    def test_custom_host_port(self):
        adapter = LMStudioAdapter({"enabled": True, "host": "192.168.1.20", "port": 5678, "model": "m"})
        assert "192.168.1.20:5678" in adapter._url("/path")

    def test_default_model(self):
        adapter = LMStudioAdapter()
        assert adapter.cfg.get("model") is not None


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLMStudioHealth:
    async def test_health_200(self):
        adapter = LMStudioAdapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, {"data": []}))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is True
        assert health.latency_ms >= 0

    async def test_health_non_200(self):
        adapter = LMStudioAdapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(503))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False

    async def test_health_connection_error(self):
        adapter = LMStudioAdapter()
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
class TestLMStudioComplete:
    async def test_complete_success(self):
        adapter = LMStudioAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, {
            "choices": [{"message": {"content": "Here's the function"}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 6, "total_tokens": 14},
        }))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "Here's the function"
        assert resp.selected_provider == "lmstudio"

    async def test_complete_http_500_returns_error(self):
        adapter = LMStudioAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(500))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "500" in resp.output.content

    async def test_complete_usage_tokens(self):
        adapter = LMStudioAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
        }))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.usage.input_tokens == 12
        assert resp.usage.output_tokens == 6
        assert resp.usage.total_tokens == 18

    async def test_complete_uses_messages_when_provided(self):
        adapter = LMStudioAdapter()
        messages = [{"role": "user", "content": "write hello world"}]
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        await adapter.complete(_make_request(messages=messages))
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["messages"] == messages

    async def test_complete_builds_message_from_objective(self):
        adapter = LMStudioAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        await adapter.complete(_make_request(objective="my local prompt", messages=[]))
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["messages"] == [{"role": "user", "content": "my local prompt"}]

    async def test_complete_uses_configured_model(self):
        adapter = LMStudioAdapter({"enabled": True, "host": "localhost", "port": 1234, "model": "phi-3", "timeout": 60})
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        await adapter.complete(_make_request())
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["model"] == "phi-3"

    async def test_complete_exception_returns_error(self):
        adapter = LMStudioAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR

    async def test_complete_latency_recorded(self):
        adapter = LMStudioAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.latency_ms >= 0
