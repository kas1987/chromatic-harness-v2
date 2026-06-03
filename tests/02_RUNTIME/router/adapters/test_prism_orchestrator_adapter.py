"""Unit tests for PrismOrchestratorAdapter."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from router.adapters.prism_orchestrator_adapter import PrismOrchestratorAdapter
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
    request_id: str = "req-prism-1",
    objective: str = "run pipeline",
    task_type: TaskType = TaskType.PLANNING,
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-prism-1",
        task_type=task_type,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _enabled_adapter(base_url: str = "http://127.0.0.1:8000") -> PrismOrchestratorAdapter:
    return PrismOrchestratorAdapter({"enabled": True, "base_url": base_url, "timeout": 60})


def _mock_response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {"output": "Prism result", "ok": True}
    resp.text = str(json_body or {})
    return resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestPrismOrchestratorAdapterInit:
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = PrismOrchestratorAdapter()
        assert adapter.enabled is False
        assert adapter.name == "prism-orchestrator"

    def test_enabled_via_env(self):
        with patch.dict(os.environ, {"PRISM_ORCHESTRATOR_ENABLED": "true"}):
            adapter = PrismOrchestratorAdapter()
        assert adapter.enabled is True

    def test_base_url_from_env(self):
        with patch.dict(os.environ, {"PRISM_ORCHESTRATOR_URL": "http://prism:9000"}):
            adapter = PrismOrchestratorAdapter()
        assert "9000" in adapter.cfg.get("base_url", "")

    def test_custom_cfg(self):
        adapter = _enabled_adapter("http://prism:8080")
        assert adapter.enabled is True
        assert "8080" in adapter.cfg.get("base_url", "")


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPrismHealth:
    async def test_health_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = PrismOrchestratorAdapter()
        health = await adapter.health()
        assert health.reachable is False
        assert "PRISM_ORCHESTRATOR_ENABLED" in health.error

    async def test_health_200(self):
        adapter = _enabled_adapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is True

    async def test_health_non_200(self):
        adapter = _enabled_adapter()
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(503))
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False

    async def test_health_exception(self):
        adapter = _enabled_adapter()
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
class TestPrismComplete:
    async def test_complete_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = PrismOrchestratorAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "PRISM_ORCHESTRATOR_ENABLED" in resp.output.content

    async def test_complete_success(self):
        adapter = _enabled_adapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, {"output": "pipeline done", "ok": True}))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "pipeline done"
        assert resp.selected_provider == "prism-orchestrator"

    async def test_complete_http_error_returns_error(self):
        adapter = _enabled_adapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(500))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "500" in resp.output.content

    async def test_complete_ok_false_returns_error(self):
        adapter = _enabled_adapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, {
            "ok": False,
            "error": "upstream failure",
            "output": None,
        }))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "upstream failure" in resp.output.content

    async def test_complete_usage_estimated_from_content_length(self):
        adapter = _enabled_adapter()
        long_output = "word " * 100  # 500 chars → ~125 tokens
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, {"output": long_output, "ok": True}))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request(objective="hello"))
        assert resp.usage.output_tokens > 0
        assert resp.usage.total_tokens >= resp.usage.output_tokens

    async def test_complete_payload_includes_task_type(self):
        adapter = _enabled_adapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        await adapter.complete(_make_request(task_type=TaskType.CODING))
        call_kwargs = mock_client.post.call_args.kwargs
        metadata = call_kwargs["json"]["metadata"]
        assert metadata["task_type"] == "coding"

    async def test_complete_payload_includes_request_id(self):
        adapter = _enabled_adapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        await adapter.complete(_make_request(request_id="prism-xyz"))
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["metadata"]["request_id"] == "prism-xyz"

    async def test_complete_exception_returns_error(self):
        adapter = _enabled_adapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR

    async def test_complete_builds_prompt_from_messages(self):
        adapter = _enabled_adapter()
        messages = [{"role": "user", "content": "part1"}, {"role": "assistant", "content": "part2"}]
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200))
        adapter._client = mock_client

        await adapter.complete(_make_request(messages=messages))
        call_kwargs = mock_client.post.call_args.kwargs
        prompt = call_kwargs["json"]["prompt"]
        assert "part1" in prompt
        assert "part2" in prompt
