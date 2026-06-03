"""Unit tests for KimiAdapter (Moonshot AI)."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from router.adapters.kimi_adapter import KimiAdapter
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
    request_id: str = "req-kimi-1",
    objective: str = "summarize the paper",
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-kimi-1",
        task_type=TaskType.RESEARCH,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _mock_response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {
        "choices": [{"message": {"content": "Kimi long-context answer"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    return resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestKimiAdapterInit:
    def test_disabled_without_key(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.delenv("MOONSHOT_API_KEY", raising=False)
            adapter = KimiAdapter()
        assert adapter.enabled is False
        assert adapter.name == "kimi"

    def test_enabled_with_key(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MOONSHOT_API_KEY", "moonshot-secret")
            adapter = KimiAdapter()
        assert adapter.enabled is True

    def test_auth_header_injected(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MOONSHOT_API_KEY", "moonshot-secret")
            adapter = KimiAdapter()
            client = adapter._get_client()
        # httpx masks Authorization values in .headers repr; check raw headers.
        auth_values = [v for k, v in client.headers.raw if k.lower() == b"authorization"]
        assert auth_values, "Authorization header missing"
        assert b"moonshot-secret" in auth_values[0]

    def test_default_base_url_is_moonshot(self):
        adapter = KimiAdapter()
        assert "moonshot" in adapter.cfg.get("base_url", "")

    def test_default_model_is_moonshot(self):
        adapter = KimiAdapter()
        assert "moonshot" in adapter.cfg.get("model", "")

    def test_custom_model(self):
        adapter = KimiAdapter({"model": "moonshot-v1-128k"})
        assert adapter.cfg["model"] == "moonshot-v1-128k"


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestKimiHealth:
    async def test_health_disabled(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.delenv("MOONSHOT_API_KEY", raising=False)
            adapter = KimiAdapter()
        health = await adapter.health()
        assert health.reachable is False
        assert "MOONSHOT_API_KEY" in health.error

    async def test_health_200(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MOONSHOT_API_KEY", "moonshot-secret")
            adapter = KimiAdapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is True

    async def test_health_exception(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MOONSHOT_API_KEY", "moonshot-secret")
            adapter = KimiAdapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestKimiComplete:
    async def test_complete_disabled(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.delenv("MOONSHOT_API_KEY", raising=False)
            adapter = KimiAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "MOONSHOT_API_KEY" in resp.output.content

    async def test_complete_success(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MOONSHOT_API_KEY", "moonshot-secret")
            adapter = KimiAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, {
            "choices": [{"message": {"content": "Kimi long answer"}}],
            "usage": {"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120},
        }))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "Kimi long answer"
        assert resp.selected_provider == "kimi"

    async def test_complete_selected_model_set(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MOONSHOT_API_KEY", "moonshot-secret")
            adapter = KimiAdapter({"model": "moonshot-v1-32k"})
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.selected_model == "moonshot-v1-32k"

    async def test_complete_http_error(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MOONSHOT_API_KEY", "moonshot-secret")
            adapter = KimiAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(503))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "503" in resp.output.content

    async def test_complete_usage_tokens(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MOONSHOT_API_KEY", "moonshot-secret")
            adapter = KimiAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
        }))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.usage.input_tokens == 50
        assert resp.usage.output_tokens == 25
        assert resp.usage.total_tokens == 75

    async def test_complete_uses_configured_base_url(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MOONSHOT_API_KEY", "moonshot-secret")
            adapter = KimiAdapter({"base_url": "https://custom.moonshot.cn/v1"})
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        await adapter.complete(_make_request())
        call_args = mock_client.post.call_args
        assert "custom.moonshot.cn" in call_args.args[0]

    async def test_complete_exception_returns_error(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("MOONSHOT_API_KEY", "moonshot-secret")
            adapter = KimiAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("read timeout"))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
