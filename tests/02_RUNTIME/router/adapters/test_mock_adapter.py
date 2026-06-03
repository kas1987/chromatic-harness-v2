"""Unit tests for MockAdapter (deterministic test stub adapter)."""

from __future__ import annotations

import pytest

from router.adapters.mock import MockAdapter
from router.adapters.base import AdapterHealth, BaseAdapter
from router.contracts import (
    ConfidenceBand,
    OutputType,
    PrivacyClass,
    RouteConfidence,
    RouteConstraints,
    RouteInput,
    RouteRequest,
    TaskType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(
    request_id: str = "req-mock-1",
    objective: str = "test objective",
    task_type: TaskType = TaskType.CODING,
    messages: list | None = None,
) -> RouteRequest:
    return RouteRequest(
        request_id=request_id,
        task_id="task-mock-1",
        task_type=task_type,
        objective=objective,
        input=RouteInput(messages=messages or []),
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestMockAdapterInit:
    def test_is_base_adapter(self):
        adapter = MockAdapter()
        assert isinstance(adapter, BaseAdapter)

    def test_name(self):
        adapter = MockAdapter()
        assert adapter.name == "mock"

    def test_always_enabled(self):
        adapter = MockAdapter()
        assert adapter.enabled is True

    def test_custom_cfg_preserved(self):
        adapter = MockAdapter({"enabled": True, "custom_key": "val"})
        assert adapter.cfg["custom_key"] == "val"


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMockAdapterHealth:
    async def test_always_reachable(self):
        adapter = MockAdapter()
        health = await adapter.health()
        assert isinstance(health, AdapterHealth)
        assert health.reachable is True
        assert health.latency_ms == 1
        assert health.error == ""


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMockAdapterComplete:
    async def test_complete_returns_text_response(self):
        adapter = MockAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.output.type == OutputType.TEXT
        assert resp.output.content != ""

    async def test_complete_includes_task_type_in_content(self):
        adapter = MockAdapter()
        resp = await adapter.complete(_make_request(task_type=TaskType.REVIEW))
        assert "review" in resp.output.content

    async def test_complete_includes_objective_in_content(self):
        adapter = MockAdapter()
        resp = await adapter.complete(_make_request(objective="my specific goal"))
        assert "my specific goal" in resp.output.content

    async def test_complete_truncates_long_objective(self):
        adapter = MockAdapter()
        long_obj = "x" * 200
        resp = await adapter.complete(_make_request(objective=long_obj))
        # The adapter truncates at 80 chars
        assert "x" * 80 in resp.output.content
        assert len(resp.output.content) < 300  # sanity check

    async def test_complete_preserves_request_id(self):
        adapter = MockAdapter()
        resp = await adapter.complete(_make_request(request_id="mock-req-abc"))
        assert resp.request_id == "mock-req-abc"

    async def test_complete_provider_is_mock(self):
        adapter = MockAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.selected_provider == "mock"

    async def test_complete_selected_model(self):
        adapter = MockAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.selected_model == "mock-v1"

    async def test_complete_route_reason(self):
        adapter = MockAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.route_reason == "mock_fallback"

    async def test_complete_zero_cost(self):
        adapter = MockAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.cost_estimate_usd == 0.0

    async def test_complete_zero_usage_tokens(self):
        adapter = MockAdapter()
        resp = await adapter.complete(_make_request())
        assert resp.usage.input_tokens == 0
        assert resp.usage.output_tokens == 0
        assert resp.usage.total_tokens == 0

    async def test_complete_confidence_score_from_request(self):
        adapter = MockAdapter()
        req = _make_request()
        req.confidence.score = 0.85
        resp = await adapter.complete(req)
        assert resp.confidence_score == 0.85

    async def test_complete_privacy_class_from_constraints(self):
        adapter = MockAdapter()
        req = _make_request()
        req.constraints.privacy_class = PrivacyClass.P3
        resp = await adapter.complete(req)
        assert resp.privacy_class == PrivacyClass.P3

    async def test_complete_multiple_task_types(self):
        adapter = MockAdapter()
        for task_type in TaskType:
            resp = await adapter.complete(_make_request(task_type=task_type))
            assert resp.output.type == OutputType.TEXT
            assert task_type.value in resp.output.content


# ---------------------------------------------------------------------------
# normalize_error (inherited from BaseAdapter)
# ---------------------------------------------------------------------------


class TestNormalizeError:
    def test_normalize_error_returns_error_output(self):
        adapter = MockAdapter()
        resp = adapter.normalize_error("req-err", "something went wrong")
        assert resp.output.type == OutputType.ERROR
        assert resp.output.content == "something went wrong"
        assert resp.request_id == "req-err"
        assert resp.selected_provider == "mock"
        assert resp.route_reason == "adapter_error"
