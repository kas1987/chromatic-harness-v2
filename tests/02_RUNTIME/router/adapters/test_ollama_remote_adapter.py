"""Unit tests for OllamaRemoteAdapter (and OllamaAdapter which wraps it)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from router.adapters.ollama_adapter import OllamaAdapter
from router.adapters.ollama_remote import OllamaRemoteAdapter
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
    request_id: str = "req-ollama-1",
    objective: str = "explain recursion",
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-oll-1",
        task_type=TaskType.CODING,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _make_remote_adapter(host: str = "localhost", port: int = 11434, model: str = "llama3.1:8b") -> OllamaRemoteAdapter:
    cfg = {"enabled": True, "host": host, "port": port, "model": model}
    return OllamaRemoteAdapter("ollama-remote", cfg)


def _mock_response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {"message": {"content": "Ollama says hello!"}}
    return resp


# ---------------------------------------------------------------------------
# OllamaRemoteAdapter — construction
# ---------------------------------------------------------------------------


class TestOllamaRemoteAdapterInit:
    def test_basic_construction(self):
        adapter = _make_remote_adapter()
        assert adapter.name == "ollama-remote"
        assert adapter.host == "localhost"
        assert adapter.port == 11434
        assert adapter.model == "llama3.1:8b"

    def test_url_construction(self):
        adapter = _make_remote_adapter(host="192.168.1.10", port=11434)
        assert adapter._url("/api/chat") == "http://192.168.1.10:11434/api/chat"

    def test_custom_host_port(self):
        adapter = _make_remote_adapter(host="desktop", port=9999)
        assert "desktop:9999" in adapter._url("/api/chat")


# ---------------------------------------------------------------------------
# OllamaRemoteAdapter — health()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOllamaRemoteHealth:
    async def test_health_ok_200(self):
        adapter = _make_remote_adapter()
        mock_resp = _mock_response(200, {"models": []})
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is True
        assert health.latency_ms >= 0

    async def test_health_non_200_returns_unreachable(self):
        adapter = _make_remote_adapter()
        mock_resp = _mock_response(503)
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False
        assert "503" in health.error

    async def test_health_connection_error(self):
        adapter = _make_remote_adapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False
        assert health.error != ""


# ---------------------------------------------------------------------------
# OllamaRemoteAdapter — complete()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOllamaRemoteComplete:
    async def test_complete_success(self):
        adapter = _make_remote_adapter()
        mock_resp = _mock_response(200, {"message": {"content": "Recursive descent!"}})
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "Recursive descent!"
        assert resp.selected_provider == "ollama-remote"

    async def test_complete_http_error_returns_error_response(self):
        adapter = _make_remote_adapter()
        mock_resp = _mock_response(500)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "500" in resp.output.content

    async def test_complete_no_model_returns_error(self):
        cfg = {"enabled": True, "host": "localhost", "port": 11434, "model": ""}
        adapter = OllamaRemoteAdapter("test-oll", cfg)

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "model" in resp.output.content.lower()

    async def test_complete_payload_uses_configured_model(self):
        adapter = _make_remote_adapter(model="mistral:7b")
        mock_resp = _mock_response(200)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        await adapter.complete(_make_request())
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["model"] == "mistral:7b"

    async def test_complete_stream_false(self):
        adapter = _make_remote_adapter()
        mock_resp = _mock_response(200)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        await adapter.complete(_make_request())
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["stream"] is False

    async def test_complete_messages_when_provided(self):
        adapter = _make_remote_adapter()
        messages = [{"role": "user", "content": "explain this"}]
        mock_resp = _mock_response(200)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        await adapter.complete(_make_request(messages=messages))
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["messages"] == messages

    async def test_complete_builds_message_from_objective(self):
        adapter = _make_remote_adapter()
        mock_resp = _mock_response(200)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        await adapter.complete(_make_request(objective="define recursion", messages=[]))
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["messages"] == [{"role": "user", "content": "define recursion"}]

    async def test_complete_exception_returns_error(self):
        adapter = _make_remote_adapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("read timeout"))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR

    async def test_complete_request_id_preserved(self):
        adapter = _make_remote_adapter()
        mock_resp = _mock_response(200)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request(request_id="oll-xyz"))
        assert resp.request_id == "oll-xyz"


# ---------------------------------------------------------------------------
# OllamaAdapter (local wrapper)
# ---------------------------------------------------------------------------


class TestOllamaAdapterWrapper:
    def test_default_construction(self):
        adapter = OllamaAdapter()
        assert adapter.name == "ollama"
        assert adapter.host == "localhost"
        assert adapter.port == 11434

    def test_custom_cfg_passed_through(self):
        adapter = OllamaAdapter({"enabled": True, "base_url": "http://192.168.1.5:11434", "model": "phi3"})
        assert adapter.model == "phi3"
