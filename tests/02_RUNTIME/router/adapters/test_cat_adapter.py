"""Unit tests for CATAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from router.adapters.cat_adapter import CATAdapter
from router.contracts import (
    OutputType,
    RouteConstraints,
    RouteInput,
    RouteRequest,
    TaskType,
)


def _enabled_adapter(base_url: str = "http://127.0.0.1:8900") -> CATAdapter:
    return CATAdapter({"enabled": True, "base_url": base_url, "timeout": 60})


def _mock_response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body or {"output": "CAT result", "ok": True}
    resp.text = str(json_body or {})
    return resp


def _make_request(
    request_id: str = "req-cat-1",
    objective: str = "run mission",
    task_type: TaskType = TaskType.PLANNING,
    messages: list | None = None,
    input_obj: RouteInput | None = None,
    constraints: RouteConstraints | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-cat-1",
        task_type=task_type,
        objective=objective,
        input=input_obj if input_obj is not None else RouteInput(messages=messages or []),
        constraints=constraints if constraints is not None else RouteConstraints(),
    )


@pytest.mark.asyncio
class TestCATComplete:
    async def test_complete_defends_missing_input(self):
        """Cloud-backed CAT must not crash when req.input is None."""
        adapter = _enabled_adapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, {"output": "ok", "ok": True}))
        adapter._client = mock_client

        req = _make_request(objective="hello")
        req.input = None  # type: ignore[assignment]
        resp = await adapter.complete(req)

        assert resp.output.type == OutputType.TEXT
        assert resp.output.content == "ok"
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["prompt"] == "hello"

    async def test_complete_defends_missing_constraints(self):
        """Cloud-backed CAT must not crash when req.constraints is None."""
        adapter = _enabled_adapter()
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, {"output": "ok", "ok": True}))
        adapter._client = mock_client

        req = _make_request()
        req.constraints = None  # type: ignore[assignment]
        resp = await adapter.complete(req)

        assert resp.output.type == OutputType.TEXT
        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["metadata"]["max_tokens"] == 8000
