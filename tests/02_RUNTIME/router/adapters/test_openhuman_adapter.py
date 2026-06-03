"""Unit tests for OpenHumanAdapter (sidecar, read-only by default)."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from router.adapters.openhuman_adapter import OpenHumanAdapter
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
    request_id: str = "req-oh-1",
    objective: str = "get personal context",
    task_type: TaskType = TaskType.PERSONAL_CONTEXT,
    messages: list | None = None,
    metadata: dict | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-oh-1",
        task_type=task_type,
        objective=objective,
        input=RouteInput(messages=messages or [], metadata=metadata or {}),
    )


def _mock_httpx_response(status_code: int = 200, json_body: dict | str | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    body = json_body if json_body is not None else {"result": "context data"}
    resp.json.return_value = body
    resp.text = str(body)
    return resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestOpenHumanAdapterInit:
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = OpenHumanAdapter()
        assert adapter.enabled is False
        assert adapter.name == "openhuman"

    def test_enabled_via_env(self):
        with patch.dict(os.environ, {"OPENHUMAN_ENABLED": "true"}):
            adapter = OpenHumanAdapter()
        assert adapter.enabled is True

    def test_base_url_from_env(self):
        with patch.dict(os.environ, {"OPENHUMAN_BASE_URL": "http://custom:9999"}):
            adapter = OpenHumanAdapter()
        assert adapter.base_url == "http://custom:9999"

    def test_auth_header_when_token_set(self):
        with patch.dict(os.environ, {"OPENHUMAN_BEARER_TOKEN": "oh-token"}):
            adapter = OpenHumanAdapter()
        assert "oh-token" in adapter.headers.get("Authorization", "")

    def test_no_auth_header_when_no_token(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = OpenHumanAdapter()
        assert adapter.headers == {}

    def test_default_mode_read_only(self):
        adapter = OpenHumanAdapter()
        assert adapter.mode == "read_only"


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOpenHumanHealth:
    async def test_health_disabled(self):
        adapter = OpenHumanAdapter({"enabled": False, "base_url": "http://127.0.0.1:8787",
                                    "env_key": "OPENHUMAN_BEARER_TOKEN", "privacy_max": "P2",
                                    "default_mode": "read_only"})
        health = await adapter.health()
        assert health.reachable is False
        assert "disabled" in health.error

    async def test_health_200(self):
        adapter = OpenHumanAdapter({"enabled": True, "base_url": "http://127.0.0.1:8787",
                                    "env_key": "OPENHUMAN_BEARER_TOKEN", "privacy_max": "P2",
                                    "default_mode": "read_only"})
        mock_resp = _mock_httpx_response(200)
        mock_async_client = MagicMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with patch("router.adapters.openhuman_adapter.httpx.AsyncClient", return_value=mock_async_client):
            health = await adapter.health()
        assert health.reachable is True

    async def test_health_non_200(self):
        adapter = OpenHumanAdapter({"enabled": True, "base_url": "http://127.0.0.1:8787",
                                    "env_key": "OPENHUMAN_BEARER_TOKEN", "privacy_max": "P2",
                                    "default_mode": "read_only"})
        mock_resp = _mock_httpx_response(503)
        mock_async_client = MagicMock()
        mock_async_client.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=mock_resp)))
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        with patch("router.adapters.openhuman_adapter.httpx.AsyncClient", return_value=mock_async_client):
            health = await adapter.health()
        assert health.reachable is False
        assert "503" in health.error


# ---------------------------------------------------------------------------
# complete() — disabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOpenHumanComplete:
    async def test_complete_disabled_returns_error_response(self):
        adapter = OpenHumanAdapter({"enabled": False, "base_url": "http://127.0.0.1:8787",
                                    "env_key": "OPENHUMAN_BEARER_TOKEN", "privacy_max": "P2",
                                    "default_mode": "read_only"})
        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert resp.route_reason == "openhuman_disabled"

    # ---------------------------------------------------------------------------
    # complete() — read-only mode blocks write actions
    # ---------------------------------------------------------------------------

    async def test_write_action_blocked_in_readonly_mode(self):
        adapter = OpenHumanAdapter({"enabled": True, "base_url": "http://127.0.0.1:8787",
                                    "env_key": "OPENHUMAN_BEARER_TOKEN", "privacy_max": "P2",
                                    "default_mode": "read_only"})
        req = _make_request(metadata={"action": "send_email"})
        resp = await adapter.complete(req)
        assert resp.output.type == OutputType.ERROR
        assert "read-only" in resp.output.content.lower() or "read_only" in resp.route_reason

    async def test_hard_write_actions_always_blocked(self):
        adapter = OpenHumanAdapter({"enabled": True, "base_url": "http://127.0.0.1:8787",
                                    "env_key": "OPENHUMAN_BEARER_TOKEN", "privacy_max": "P2",
                                    "default_mode": "read_only"})
        for action in ["delete_files", "write_chromatic_memory", "modify_calendar"]:
            req = _make_request(metadata={"action": action})
            resp = await adapter.complete(req)
            assert resp.output.type == OutputType.ERROR, f"Expected error for action: {action}"

    # ---------------------------------------------------------------------------
    # complete() — allowed read actions
    # ---------------------------------------------------------------------------

    async def test_memory_search_allowed(self):
        adapter = OpenHumanAdapter({"enabled": True, "base_url": "http://127.0.0.1:8787",
                                    "env_key": "OPENHUMAN_BEARER_TOKEN", "privacy_max": "P2",
                                    "default_mode": "read_only"})
        mock_resp = _mock_httpx_response(200, {"result": "memory found"})
        mock_async_client = MagicMock()
        inner_client = MagicMock()
        inner_client.post = AsyncMock(return_value=mock_resp)
        mock_async_client.__aenter__ = AsyncMock(return_value=inner_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        req = _make_request(metadata={"action": "memory_search"})
        with patch("router.adapters.openhuman_adapter.httpx.AsyncClient", return_value=mock_async_client):
            resp = await adapter.complete(req)

        assert resp.output.type != OutputType.ERROR or resp.route_reason not in (
            "openhuman_readonly_blocked", "openhuman_write_blocked"
        )

    async def test_complete_success_json_response(self):
        adapter = OpenHumanAdapter({"enabled": True, "base_url": "http://127.0.0.1:8787",
                                    "env_key": "OPENHUMAN_BEARER_TOKEN", "privacy_max": "P2",
                                    "default_mode": "read_only"})
        response_data = {"answer": "context result"}
        mock_resp = _mock_httpx_response(200, response_data)
        mock_async_client = MagicMock()
        inner_client = MagicMock()
        inner_client.post = AsyncMock(return_value=mock_resp)
        mock_async_client.__aenter__ = AsyncMock(return_value=inner_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        req = _make_request(metadata={"action": "memory_search"})
        with patch("router.adapters.openhuman_adapter.httpx.AsyncClient", return_value=mock_async_client):
            resp = await adapter.complete(req)

        assert resp.request_id == "req-oh-1"
        assert resp.selected_provider == "openhuman"
        assert resp.route_reason == "openhuman_ok"

    async def test_complete_http_error_response(self):
        adapter = OpenHumanAdapter({"enabled": True, "base_url": "http://127.0.0.1:8787",
                                    "env_key": "OPENHUMAN_BEARER_TOKEN", "privacy_max": "P2",
                                    "default_mode": "read_only"})
        mock_resp = _mock_httpx_response(500)
        mock_async_client = MagicMock()
        inner_client = MagicMock()
        inner_client.post = AsyncMock(return_value=mock_resp)
        mock_async_client.__aenter__ = AsyncMock(return_value=inner_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        req = _make_request(metadata={"action": "context_query"})
        with patch("router.adapters.openhuman_adapter.httpx.AsyncClient", return_value=mock_async_client):
            resp = await adapter.complete(req)

        assert resp.output.type == OutputType.ERROR
        assert resp.route_reason == "openhuman_http_error"

    async def test_complete_exception_returns_error(self):
        adapter = OpenHumanAdapter({"enabled": True, "base_url": "http://127.0.0.1:8787",
                                    "env_key": "OPENHUMAN_BEARER_TOKEN", "privacy_max": "P2",
                                    "default_mode": "read_only"})
        mock_async_client = MagicMock()
        inner_client = MagicMock()
        inner_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_async_client.__aenter__ = AsyncMock(return_value=inner_client)
        mock_async_client.__aexit__ = AsyncMock(return_value=False)

        req = _make_request(metadata={"action": "context_query"})
        with patch("router.adapters.openhuman_adapter.httpx.AsyncClient", return_value=mock_async_client):
            resp = await adapter.complete(req)

        assert resp.output.type == OutputType.ERROR
        assert resp.route_reason == "openhuman_exception"


# ---------------------------------------------------------------------------
# _action_from_request (sync, separate class)
# ---------------------------------------------------------------------------

class TestOpenHumanActionFromRequest:
    def test_action_from_metadata(self):
        adapter = OpenHumanAdapter()
        req = _make_request(metadata={"action": "context_query"})
        action = adapter._action_from_request(req)
        assert action == "context_query"

    def test_action_mapped_from_task_type_personal_context(self):
        adapter = OpenHumanAdapter()
        req = _make_request(task_type=TaskType.PERSONAL_CONTEXT, metadata={})
        action = adapter._action_from_request(req)
        assert action == "memory_search"

    def test_action_mapped_from_task_type_research(self):
        adapter = OpenHumanAdapter()
        req = _make_request(task_type=TaskType.RESEARCH, metadata={})
        action = adapter._action_from_request(req)
        assert action == "context_query"
