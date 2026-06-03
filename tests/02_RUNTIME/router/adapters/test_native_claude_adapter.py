"""Unit tests for NativeClaudeAdapter (relay + subprocess modes)."""
from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from router.adapters.native_claude_adapter import NativeClaudeAdapter
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
    request_id: str = "req-nc-1",
    objective: str = "explain closures",
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-nc-1",
        task_type=TaskType.CODING,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _relay_adapter(relay_url: str = "http://relay:5000") -> NativeClaudeAdapter:
    return NativeClaudeAdapter({"enabled": True, "relay_url": relay_url, "model": "claude-haiku"})


def _mock_httpx_response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {"result": "relay answer", "usage": {"input_tokens": 5, "output_tokens": 3}}
    resp.text = str(json_body or {})
    return resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestNativeClaudeAdapterInit:
    def test_disabled_without_relay_or_cli(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("router.adapters.native_claude_adapter.shutil.which", return_value=None):
                adapter = NativeClaudeAdapter()
        assert adapter.enabled is False

    def test_enabled_with_relay_url(self):
        with patch.dict(os.environ, {"NATIVE_CLAUDE_RELAY_URL": "http://relay:5000"}):
            adapter = NativeClaudeAdapter()
        assert adapter.enabled is True

    def test_enabled_with_cli_in_path(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("router.adapters.native_claude_adapter.shutil.which", return_value="/usr/bin/claude"):
                adapter = NativeClaudeAdapter()
        assert adapter.enabled is True

    def test_use_relay_true_when_relay_url_set(self):
        adapter = _relay_adapter()
        assert adapter._use_relay() is True

    def test_use_relay_false_when_no_url(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("router.adapters.native_claude_adapter.shutil.which", return_value="/usr/bin/claude"):
                adapter = NativeClaudeAdapter()
        assert adapter._use_relay() is False

    def test_name_is_native_claude(self):
        adapter = NativeClaudeAdapter()
        assert adapter.name == "native_claude"


# ---------------------------------------------------------------------------
# health() — disabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestNativeClaudeHealth:
    async def test_health_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("router.adapters.native_claude_adapter.shutil.which", return_value=None):
                adapter = NativeClaudeAdapter()
        health = await adapter.health()
        assert health.reachable is False
        assert "relay" in health.error.lower() or "claude" in health.error.lower()

    async def test_health_relay_200(self):
        adapter = _relay_adapter()
        mock_resp = _mock_httpx_response(200)
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._http = mock_client

        health = await adapter.health()
        assert health.reachable is True

    async def test_health_relay_non_200(self):
        adapter = _relay_adapter()
        mock_resp = _mock_httpx_response(503)
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        adapter._http = mock_client

        health = await adapter.health()
        assert health.reachable is False

    async def test_health_relay_exception(self):
        adapter = _relay_adapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        adapter._http = mock_client

        health = await adapter.health()
        assert health.reachable is False
        assert health.error != ""


# ---------------------------------------------------------------------------
# complete() — disabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestNativeClaudeComplete:
    async def test_complete_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("router.adapters.native_claude_adapter.shutil.which", return_value=None):
                adapter = NativeClaudeAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "native_claude" in resp.output.content

    # -------------------------------------------------------------------------
    # Relay mode
    # -------------------------------------------------------------------------

    async def test_complete_relay_success(self):
        adapter = _relay_adapter()
        mock_resp = _mock_httpx_response(200, {
            "result": "relay content",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._http = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "relay content"
        assert resp.selected_provider == "native_claude"

    async def test_complete_relay_usage(self):
        adapter = _relay_adapter()
        mock_resp = _mock_httpx_response(200, {
            "result": "answer",
            "usage": {"input_tokens": 20, "output_tokens": 8},
        })
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._http = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.usage.input_tokens == 20
        assert resp.usage.output_tokens == 8
        assert resp.usage.total_tokens == 28

    async def test_complete_relay_http_error(self):
        adapter = _relay_adapter()
        mock_resp = _mock_httpx_response(503)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._http = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "503" in resp.output.content

    async def test_complete_relay_exception(self):
        adapter = _relay_adapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        adapter._http = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR

    async def test_complete_relay_sends_system_prompt(self):
        adapter = _relay_adapter()
        messages = [
            {"role": "system", "content": "be concise"},
            {"role": "user", "content": "hello"},
        ]
        mock_resp = _mock_httpx_response(200, {"result": "ok", "usage": {}})
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        adapter._http = mock_client

        await adapter.complete(_make_request(messages=messages))
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"].get("system") is not None

    # -------------------------------------------------------------------------
    # Subprocess mode
    # -------------------------------------------------------------------------

    async def test_complete_subprocess_success(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("router.adapters.native_claude_adapter.shutil.which", return_value="/usr/bin/claude"):
                adapter = NativeClaudeAdapter({"enabled": True, "relay_url": "", "model": "claude-haiku"})

        output = json.dumps({"result": "subprocess answer", "usage": {"input_tokens": 3, "output_tokens": 2}})
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(output.encode(), b""))

        with patch("router.adapters.native_claude_adapter.asyncio.create_subprocess_exec",
                   AsyncMock(return_value=mock_proc)):
            resp = await adapter.complete(_make_request())

        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "subprocess answer"

    async def test_complete_subprocess_nonzero_exit_returns_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("router.adapters.native_claude_adapter.shutil.which", return_value="/usr/bin/claude"):
                adapter = NativeClaudeAdapter({"enabled": True, "relay_url": "", "model": "claude-haiku"})

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error message"))

        with patch("router.adapters.native_claude_adapter.asyncio.create_subprocess_exec",
                   AsyncMock(return_value=mock_proc)):
            resp = await adapter.complete(_make_request())

        assert resp.output.type == OutputType.ERROR
        assert "exit 1" in resp.output.content

    async def test_complete_subprocess_is_error_flag(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("router.adapters.native_claude_adapter.shutil.which", return_value="/usr/bin/claude"):
                adapter = NativeClaudeAdapter({"enabled": True, "relay_url": "", "model": "claude-haiku"})

        output = json.dumps({"is_error": True, "result": "error occurred"})
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(output.encode(), b""))

        with patch("router.adapters.native_claude_adapter.asyncio.create_subprocess_exec",
                   AsyncMock(return_value=mock_proc)):
            resp = await adapter.complete(_make_request())

        assert resp.output.type == OutputType.ERROR

    async def test_complete_subprocess_timeout_returns_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("router.adapters.native_claude_adapter.shutil.which", return_value="/usr/bin/claude"):
                adapter = NativeClaudeAdapter({"enabled": True, "relay_url": "", "model": "claude-haiku", "timeout": 1})

        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("router.adapters.native_claude_adapter.asyncio.create_subprocess_exec",
                   AsyncMock(return_value=mock_proc)):
            resp = await adapter.complete(_make_request())

        assert resp.output.type == OutputType.ERROR
        assert "timed out" in resp.output.content
