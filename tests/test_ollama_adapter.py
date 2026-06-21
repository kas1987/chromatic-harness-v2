"""Tests for src/chromatic_router/adapters/ollama_adapter.py and
the underlying OllamaRemoteAdapter in 02_RUNTIME/router/adapters/ollama_remote.py.

All HTTP calls are monkeypatched — no real Ollama instance is needed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_RUNTIME = _REPO / "02_RUNTIME"
_SRC = _REPO / "src"

for _p in (str(_REPO), str(_RUNTIME), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Helpers to build minimal RouteRequest objects
# ---------------------------------------------------------------------------

def _make_request(request_id: str = "req-001", objective: str = "hello", messages=None):
    from router.contracts import (
        RouteRequest, RouteInput, RouteConstraints, RouteConfidence,
        TaskType,
    )
    return RouteRequest(
        request_id=request_id,
        task_id="task-1",
        task_type=TaskType.CLASSIFICATION,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


# ---------------------------------------------------------------------------
# Helper: fake httpx response
# ---------------------------------------------------------------------------

def _fake_httpx_response(status: int = 200, json_body: dict | None = None):
    resp = MagicMock()
    resp.status_code = status
    resp.json = MagicMock(return_value=json_body or {
        "message": {"content": "mocked response text"}
    })
    return resp


# ---------------------------------------------------------------------------
# TestOllamaAdapter
# ---------------------------------------------------------------------------

class TestOllamaAdapter:

    # ── _prune_messages ──────────────────────────────────────────────────────

    def test_prune_messages_no_op_when_within_limit(self):
        """Messages within max_turns are returned unchanged."""
        from router.adapters.ollama_remote import _prune_messages
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
        result = _prune_messages(msgs, max_turns=10)
        assert result == msgs

    def test_prune_messages_keeps_system_always(self):
        """System messages are preserved even when non-system turns exceed the cap."""
        from router.adapters.ollama_remote import _prune_messages
        system = {"role": "system", "content": "instructions"}
        # 6 user+assistant pairs (12 msgs) but cap is 2 turns (4 msgs)
        convs = []
        for i in range(6):
            convs.append({"role": "user", "content": f"u{i}"})
            convs.append({"role": "assistant", "content": f"a{i}"})
        result = _prune_messages([system] + convs, max_turns=2)
        assert result[0] == system
        # Only the last 2 pairs remain for non-system
        assert len(result) == 1 + 4

    def test_prune_messages_zero_means_keep_all(self):
        """max_turns=0 disables pruning."""
        from router.adapters.ollama_remote import _prune_messages
        msgs = [{"role": "user", "content": str(i)} for i in range(100)]
        result = _prune_messages(msgs, max_turns=0)
        assert len(result) == 100

    def test_prune_messages_empty_input(self):
        """Empty message list returns empty list."""
        from router.adapters.ollama_remote import _prune_messages
        assert _prune_messages([], max_turns=5) == []

    # ── OllamaRemoteAdapter construction ────────────────────────────────────

    def test_remote_adapter_defaults(self):
        """OllamaRemoteAdapter stores host/port/model from cfg."""
        from router.adapters.ollama_remote import OllamaRemoteAdapter
        adapter = OllamaRemoteAdapter("ollama", {"host": "192.168.1.10", "port": 11434, "model": "mistral"})
        assert adapter.host == "192.168.1.10"
        assert adapter.port == 11434
        assert adapter.model == "mistral"

    def test_remote_adapter_url_construction(self):
        """_url() builds correct http://host:port/path string."""
        from router.adapters.ollama_remote import OllamaRemoteAdapter
        adapter = OllamaRemoteAdapter("ollama", {"host": "gpu-box", "port": 11434, "model": "x"})
        assert adapter._url("/api/tags") == "http://gpu-box:11434/api/tags"

    # ── health() ────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_returns_reachable_on_200(self, monkeypatch):
        """health() returns AdapterHealth(reachable=True) when /api/tags → 200."""
        from router.adapters.ollama_remote import OllamaRemoteAdapter

        fake_resp = _fake_httpx_response(status=200)
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=fake_resp)

        adapter = OllamaRemoteAdapter("ollama", {"host": "localhost", "port": 11434, "model": "m"})
        monkeypatch.setattr(adapter, "_get_client", lambda: mock_client)

        health = await adapter.health()
        assert health.reachable is True
        assert health.error == ""

    @pytest.mark.asyncio
    async def test_health_returns_unreachable_on_non_200(self, monkeypatch):
        """health() returns AdapterHealth(reachable=False) on non-200 status."""
        from router.adapters.ollama_remote import OllamaRemoteAdapter

        fake_resp = _fake_httpx_response(status=503)
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=fake_resp)

        adapter = OllamaRemoteAdapter("ollama", {"host": "localhost", "port": 11434, "model": "m"})
        monkeypatch.setattr(adapter, "_get_client", lambda: mock_client)

        health = await adapter.health()
        assert health.reachable is False
        assert "503" in health.error

    @pytest.mark.asyncio
    async def test_health_returns_unreachable_on_exception(self, monkeypatch):
        """health() catches connection errors and marks reachable=False."""
        from router.adapters.ollama_remote import OllamaRemoteAdapter

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))

        adapter = OllamaRemoteAdapter("ollama", {"host": "dead-host", "port": 11434, "model": "m"})
        monkeypatch.setattr(adapter, "_get_client", lambda: mock_client)

        health = await adapter.health()
        assert health.reachable is False
        assert "refused" in health.error

    # ── complete() ──────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_complete_returns_text_content(self, monkeypatch):
        """complete() returns RouteResponse with the model's message content."""
        from router.adapters.ollama_remote import OllamaRemoteAdapter
        from router.contracts import OutputType

        fake_resp = _fake_httpx_response(200, {"message": {"content": "hello world"}})
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=fake_resp)

        adapter = OllamaRemoteAdapter("ollama", {"host": "localhost", "port": 11434, "model": "llama3"})
        monkeypatch.setattr(adapter, "_get_client", lambda: mock_client)

        req = _make_request(objective="ping")
        resp = await adapter.complete(req)

        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "hello world"
        assert resp.selected_provider == "ollama"

    @pytest.mark.asyncio
    async def test_complete_uses_objective_when_no_messages(self, monkeypatch):
        """complete() falls back to objective when messages list is empty."""
        from router.adapters.ollama_remote import OllamaRemoteAdapter

        captured: list = []

        async def fake_post(url, *, json=None, **kw):
            captured.append(json)
            return _fake_httpx_response(200, {"message": {"content": "ok"}})

        mock_client = MagicMock()
        mock_client.post = fake_post

        adapter = OllamaRemoteAdapter("ollama", {"host": "localhost", "port": 11434, "model": "llama3"})
        monkeypatch.setattr(adapter, "_get_client", lambda: mock_client)

        req = _make_request(objective="my objective", messages=[])
        await adapter.complete(req)

        assert captured[0]["messages"][0]["content"] == "my objective"

    @pytest.mark.asyncio
    async def test_complete_error_on_non_200(self, monkeypatch):
        """complete() returns an ERROR output when Ollama returns non-200."""
        from router.adapters.ollama_remote import OllamaRemoteAdapter
        from router.contracts import OutputType

        fake_resp = _fake_httpx_response(status=500)
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=fake_resp)

        adapter = OllamaRemoteAdapter("ollama", {"host": "localhost", "port": 11434, "model": "llama3"})
        monkeypatch.setattr(adapter, "_get_client", lambda: mock_client)

        req = _make_request()
        resp = await adapter.complete(req)

        assert resp.output.type == OutputType.ERROR

    @pytest.mark.asyncio
    async def test_complete_error_on_exception(self, monkeypatch):
        """complete() catches exceptions and returns ERROR RouteResponse."""
        from router.adapters.ollama_remote import OllamaRemoteAdapter
        from router.contracts import OutputType

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=TimeoutError("timeout"))

        adapter = OllamaRemoteAdapter("ollama", {"host": "localhost", "port": 11434, "model": "llama3"})
        monkeypatch.setattr(adapter, "_get_client", lambda: mock_client)

        req = _make_request()
        resp = await adapter.complete(req)

        assert resp.output.type == OutputType.ERROR
        assert "timeout" in resp.output.content.lower() or len(resp.logs.errors) > 0

    @pytest.mark.asyncio
    async def test_complete_no_model_configured(self, monkeypatch):
        """complete() returns ERROR immediately when model is empty string."""
        from router.adapters.ollama_remote import OllamaRemoteAdapter
        from router.contracts import OutputType

        adapter = OllamaRemoteAdapter("ollama", {"host": "localhost", "port": 11434, "model": ""})

        req = _make_request()
        resp = await adapter.complete(req)

        assert resp.output.type == OutputType.ERROR

    # ── OllamaAdapter (src wrapper) ──────────────────────────────────────────

    def test_ollama_adapter_inherits_remote(self):
        """OllamaAdapter from src/ is a subclass of OllamaRemoteAdapter."""
        from chromatic_router.adapters.ollama_adapter import OllamaAdapter
        from router.adapters.ollama_remote import OllamaRemoteAdapter
        assert issubclass(OllamaAdapter, OllamaRemoteAdapter)

    def test_ollama_adapter_default_cfg(self):
        """OllamaAdapter() with no cfg defaults to localhost:11434."""
        from chromatic_router.adapters.ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter()
        assert adapter.host == "localhost" or adapter.cfg.get("base_url", "").startswith("http://localhost")

    def test_ollama_adapter_custom_cfg(self):
        """OllamaAdapter accepts a custom cfg dict."""
        from chromatic_router.adapters.ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter({"enabled": True, "base_url": "http://gpu-box:11434", "host": "gpu-box"})
        assert adapter.enabled is True
