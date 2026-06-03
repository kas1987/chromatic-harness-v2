"""Unit tests for the FeatherlessAdapter."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from router.adapters.featherless_adapter import FeatherlessAdapter
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
    request_id: str = "req-fl-1",
    objective: str = "classify intent",
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-fl-1",
        task_type=TaskType.CLASSIFICATION,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _mock_response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {
        "choices": [{"message": {"content": "Featherless answer"}}],
        "usage": {"prompt_tokens": 6, "completion_tokens": 3, "total_tokens": 9},
    }
    return resp


# ---------------------------------------------------------------------------
# Construction / auth
# ---------------------------------------------------------------------------


class TestFeatherlessAdapterInit:
    def test_disabled_without_key(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.delenv("FEATHERLESS_API_KEY", raising=False)
            adapter = FeatherlessAdapter()
        assert adapter.enabled is False
        assert adapter.name == "featherless"

    def test_enabled_with_key(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("FEATHERLESS_API_KEY", "fl-secret")
            adapter = FeatherlessAdapter()
        assert adapter.enabled is True

    def test_auth_header_injected(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("FEATHERLESS_API_KEY", "fl-secret")
            adapter = FeatherlessAdapter()
            client = adapter._get_client()
        # httpx masks the Authorization header value in headers repr;
        # verify via the raw headers iterator which shows the actual value.
        auth_values = [v for k, v in client.headers.raw if k.lower() == b"authorization"]
        assert auth_values, "Authorization header missing"
        assert b"fl-secret" in auth_values[0]

    def test_default_model_is_llama(self):
        adapter = FeatherlessAdapter()
        assert "llama" in adapter.cfg.get("model", "").lower()


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFeatherlessHealth:
    async def test_health_disabled(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.delenv("FEATHERLESS_API_KEY", raising=False)
            adapter = FeatherlessAdapter()
        health = await adapter.health()
        assert health.reachable is False
        assert "FEATHERLESS_API_KEY" in health.error

    async def test_health_200(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("FEATHERLESS_API_KEY", "fl-secret")
            adapter = FeatherlessAdapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is True

    async def test_health_non_200(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("FEATHERLESS_API_KEY", "fl-secret")
            adapter = FeatherlessAdapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(503))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False

    async def test_health_exception(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("FEATHERLESS_API_KEY", "fl-secret")
            adapter = FeatherlessAdapter()
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
class TestFeatherlessComplete:
    async def test_complete_disabled(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.delenv("FEATHERLESS_API_KEY", raising=False)
            adapter = FeatherlessAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "FEATHERLESS_API_KEY" in resp.output.content

    async def test_complete_success(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("FEATHERLESS_API_KEY", "fl-secret")
            adapter = FeatherlessAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=_mock_response(
                200,
                {
                    "choices": [{"message": {"content": "classified!"}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
                },
            )
        )
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "classified!"
        assert resp.selected_provider == "featherless"

    async def test_complete_http_429_returns_error(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("FEATHERLESS_API_KEY", "fl-secret")
            adapter = FeatherlessAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(429))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "429" in resp.output.content

    async def test_complete_usage_tokens(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("FEATHERLESS_API_KEY", "fl-secret")
            adapter = FeatherlessAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            return_value=_mock_response(
                200,
                {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 15, "completion_tokens": 7, "total_tokens": 22},
                },
            )
        )
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.usage.input_tokens == 15
        assert resp.usage.output_tokens == 7
        assert resp.usage.total_tokens == 22

    async def test_complete_exception_returns_error(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("FEATHERLESS_API_KEY", "fl-secret")
            adapter = FeatherlessAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR

    async def test_complete_request_id_preserved(self):
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("FEATHERLESS_API_KEY", "fl-secret")
            adapter = FeatherlessAdapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request(request_id="fl-req-99"))
        assert resp.request_id == "fl-req-99"
