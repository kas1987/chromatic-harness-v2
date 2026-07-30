"""Unit tests for the Agnes adapter."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from router.adapters.base import AdapterError
from router.adapters.agnes_adapter import AgnesAdapter
from router.contracts import OutputType, RouteInput, RouteRequest, TaskType


def _make_request(
    request_id: str = "req-agnes-1",
    objective: str = "translate this",
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-agnes-1",
        task_type=TaskType.CODING,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


def _fake_completion(content: str = "Agnes says hi", prompt_tokens: int = 12, completion_tokens: int = 5):
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


class TestAgnesAdapterInit:
    def test_disabled_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = AgnesAdapter()
        assert adapter.enabled is False
        assert adapter.name == "agnes"

    def test_enabled_with_key(self):
        with patch.dict(os.environ, {"AGNES_API_KEY": "agnes-test"}):
            adapter = AgnesAdapter()
        assert adapter.enabled is True
        assert adapter.cfg["base_url"] == "https://apihub.agnes-ai.com/v1"
        assert adapter.cfg["model"] == "agnes-2.5-flash"


class TestAgnesGetClient:
    def test_raises_adapter_error_when_sdk_missing(self):
        with patch.dict(os.environ, {"AGNES_API_KEY": "agnes-test"}):
            adapter = AgnesAdapter()
        with patch.dict("sys.modules", {"openai": None}):
            adapter._client = None
            with pytest.raises(AdapterError) as exc_info:
                adapter._get_client()
        assert "openai" in str(exc_info.value).lower()
        assert exc_info.value.provider == "agnes"


class TestAgnesRetryPolicy:
    def test_retries_rate_limit_and_server_errors(self):
        with patch.dict(os.environ, {"AGNES_API_KEY": "agnes-test"}):
            adapter = AgnesAdapter()

        class _FakeErr(Exception):
            def __init__(self, status_code: int):
                self.status_code = status_code

        assert adapter._should_retry(_FakeErr(429)) is True
        assert adapter._should_retry(_FakeErr(503)) is True
        assert adapter._should_retry(_FakeErr(400)) is False


@pytest.mark.asyncio
class TestAgnesAdapterComplete:
    async def test_complete_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            adapter = AgnesAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.ERROR
        assert "AGNES_API_KEY" in resp.output.content

    async def test_complete_success(self):
        with patch.dict(os.environ, {"AGNES_API_KEY": "agnes-test"}):
            adapter = AgnesAdapter()
        fake = _fake_completion("Hello from Agnes", 10, 4)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "Hello from Agnes"
        assert resp.selected_provider == "agnes"

    async def test_complete_uses_configured_temperature(self):
        with patch.dict(os.environ, {"AGNES_API_KEY": "agnes-test"}):
            adapter = AgnesAdapter({"temperature": 0.15})
        fake = _fake_completion("Hello from Agnes", 10, 4)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=fake)
        adapter._client = mock_client

        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["temperature"] == 0.15

    async def test_complete_retries_with_jitter_delay(self):
        with patch.dict(os.environ, {"AGNES_API_KEY": "agnes-test"}):
            adapter = AgnesAdapter(
                {
                    "max_retries": 2,
                    "retry_base_delay_s": 1.0,
                    "retry_max_delay_s": 4.0,
                    "retry_max_attempt_interval_s": 5.0,
                    "retry_jitter_ratio": 0.5,
                }
            )

        class TimeoutBoom(Exception):
            pass

        fake = _fake_completion("retry ok", 10, 4)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[TimeoutBoom("temporary"), fake])
        adapter._client = mock_client

        with (
            patch("router.adapters.agnes_adapter.random.uniform", return_value=0.4),
            patch("router.adapters.agnes_adapter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            resp = await adapter.complete(_make_request())

        assert resp.output.type == OutputType.TEXT
        assert mock_client.chat.completions.create.await_count == 2
        mock_sleep.assert_awaited_once_with(1.4)
        assert any(evt.startswith("retry_event=") for evt in resp.logs.policy_checks)

    async def test_complete_caps_retry_delay_with_max_attempt_interval(self):
        with patch.dict(os.environ, {"AGNES_API_KEY": "agnes-test"}):
            adapter = AgnesAdapter(
                {
                    "max_retries": 2,
                    "retry_base_delay_s": 2.0,
                    "retry_max_delay_s": 10.0,
                    "retry_max_attempt_interval_s": 0.3,
                    "retry_jitter_ratio": 0.5,
                }
            )

        class TimeoutBoom(Exception):
            pass

        fake = _fake_completion("retry ok", 10, 4)
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[TimeoutBoom("temporary"), fake])
        adapter._client = mock_client

        with (
            patch("router.adapters.agnes_adapter.random.uniform", return_value=0.9),
            patch("router.adapters.agnes_adapter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            resp = await adapter.complete(_make_request())

        assert resp.output.type == OutputType.TEXT
        mock_sleep.assert_awaited_once_with(0.3)

    async def test_complete_stops_when_retry_elapsed_budget_is_exhausted(self):
        with patch.dict(os.environ, {"AGNES_API_KEY": "agnes-test"}):
            adapter = AgnesAdapter(
                {
                    "max_retries": 3,
                    "retry_base_delay_s": 1.0,
                    "retry_max_delay_s": 4.0,
                    "retry_max_elapsed_s": 0.0,
                }
            )

        class TimeoutBoom(Exception):
            pass

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=TimeoutBoom("temporary"))
        adapter._client = mock_client

        with patch("router.adapters.agnes_adapter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            resp = await adapter.complete(_make_request())

        assert resp.output.type == OutputType.ERROR
        assert mock_client.chat.completions.create.await_count == 1
        mock_sleep.assert_not_awaited()
