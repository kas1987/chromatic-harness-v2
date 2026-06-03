"""Unit tests for the GoogleAdapter (google-genai SDK)."""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from router.adapters.base import AdapterError
from router.adapters.google_adapter import GoogleAdapter
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
    request_id: str = "req-goog-1",
    objective: str = "summarize this",
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-goog-1",
        task_type=TaskType.RESEARCH,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _fake_generate_response(text: str = "Gemini response", blocked: bool = False):
    usage = SimpleNamespace(
        prompt_token_count=10,
        candidates_token_count=5,
        total_token_count=15,
    )
    feedback = SimpleNamespace(block_reason=("SAFETY" if blocked else None))
    resp = MagicMock()
    resp.text = text if not blocked else ""
    resp.usage_metadata = usage
    resp.prompt_feedback = feedback
    return resp


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestGoogleAdapterInit:
    def test_disabled_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = GoogleAdapter()
        assert adapter.enabled is False
        assert adapter.name == "google"

    def test_enabled_with_key(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        assert adapter.enabled is True

    def test_default_model_is_gemini(self):
        adapter = GoogleAdapter()
        assert "gemini" in adapter.cfg.get("model", "").lower()

    def test_custom_model(self):
        adapter = GoogleAdapter({"model": "gemini-pro"})
        assert adapter.cfg["model"] == "gemini-pro"


# ---------------------------------------------------------------------------
# _get_client
# ---------------------------------------------------------------------------

class TestGoogleGetClient:
    def test_raises_adapter_error_when_sdk_missing(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "key"}):
            adapter = GoogleAdapter()
        with patch.dict("sys.modules", {"google": None, "google.genai": None}):
            adapter._client = None
            with pytest.raises(AdapterError) as exc_info:
                adapter._get_client()
        assert "google-genai" in str(exc_info.value)
        assert exc_info.value.provider == "google"

    def test_returns_cached_client(self):
        adapter = GoogleAdapter()
        sentinel = MagicMock()
        adapter._client = sentinel
        assert adapter._get_client() is sentinel


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGoogleAdapterHealth:
    async def test_health_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = GoogleAdapter()
        health = await adapter.health()
        assert health.reachable is False
        assert "GOOGLE_API_KEY" in health.error

    async def test_health_reachable(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        mock_client = MagicMock()
        # models.list returns an iterable
        mock_client.models.list.return_value = iter([MagicMock()])
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is True
        assert health.latency_ms >= 0

    async def test_health_exception(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        mock_client = MagicMock()
        mock_client.models.list.side_effect = RuntimeError("quota exceeded")
        adapter._client = mock_client

        health = await adapter.health()
        assert health.reachable is False
        assert "quota exceeded" in health.error


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGoogleAdapterComplete:
    async def test_complete_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = GoogleAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "GOOGLE_API_KEY" in resp.output.content

    async def test_complete_success(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _fake_generate_response("Gemini says hi!")
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "Gemini says hi!"
        assert resp.selected_provider == "google"

    async def test_complete_uses_message_contents(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _fake_generate_response("ok")
        adapter._client = mock_client

        messages = [{"role": "user", "content": "first"}, {"role": "user", "content": "second"}]
        await adapter.complete(_make_request(messages=messages))

        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        assert "first" in call_kwargs["contents"]
        assert "second" in call_kwargs["contents"]

    async def test_complete_falls_back_to_objective(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _fake_generate_response("ok")
        adapter._client = mock_client

        await adapter.complete(_make_request(objective="my objective", messages=[]))
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        assert call_kwargs["contents"] == "my objective"

    async def test_complete_usage_tokens(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _fake_generate_response("result")
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.usage.input_tokens == 10
        assert resp.usage.output_tokens == 5
        assert resp.usage.total_tokens == 15

    async def test_complete_blocked_response_returns_error(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        mock_client = MagicMock()
        blocked_resp = _fake_generate_response(blocked=True)
        mock_client.models.generate_content.return_value = blocked_resp
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR

    async def test_complete_empty_text_returns_error(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        mock_client = MagicMock()
        empty_resp = MagicMock()
        empty_resp.text = ""
        empty_resp.prompt_feedback = SimpleNamespace(block_reason=None)
        empty_resp.usage_metadata = SimpleNamespace(
            prompt_token_count=0, candidates_token_count=0, total_token_count=0
        )
        mock_client.models.generate_content.return_value = empty_resp
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "Empty" in resp.output.content or resp.output.content != ""

    async def test_complete_exception_returns_error(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("network error")
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "network error" in resp.output.content

    async def test_complete_request_id_preserved(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gapi-secret"}):
            adapter = GoogleAdapter()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _fake_generate_response("ok")
        adapter._client = mock_client

        resp = await adapter.complete(_make_request(request_id="goog-abc"))
        assert resp.request_id == "goog-abc"
