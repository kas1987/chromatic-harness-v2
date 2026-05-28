"""Integration tests for OpenHuman sidecar adapter."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_RUNTIME = os.path.join(_REPO, "02_RUNTIME")
sys.path.insert(0, _REPO)
sys.path.insert(0, _RUNTIME)

import pytest
from router.adapters.openhuman_adapter import OpenHumanAdapter
from router.contracts import RouteRequest, RouteInput, TaskType, RouteConstraints


@pytest.fixture
def openhuman_config():
    return {
        "enabled": True,
        "base_url": "http://localhost:8787",
        "env_key": "OPENHUMAN_BEARER_TOKEN",
        "default_mode": "read_only",
    }


@pytest.fixture
def openhuman_adapter(openhuman_config):
    return OpenHumanAdapter(cfg=openhuman_config)


@pytest.fixture
def route_request():
    return RouteRequest(
        request_id="test-123",
        task_id="task-123",
        task_type=TaskType.RESEARCH,
        objective="Find information about Claude",
        input=RouteInput(messages=[], metadata={}),
        constraints=RouteConstraints(),
    )


@pytest.mark.asyncio
async def test_openhuman_disabled(openhuman_config, route_request):
    """Test that disabled adapter returns error."""
    openhuman_config["enabled"] = False
    adapter = OpenHumanAdapter(cfg=openhuman_config)
    response = await adapter.complete(route_request)
    assert response.output.type.value == "error"
    assert "disabled" in response.output.content.lower()


@pytest.mark.asyncio
async def test_openhuman_readonly_blocks_write_action(openhuman_config, route_request):
    """Test that read-only mode blocks write actions."""
    adapter = OpenHumanAdapter(cfg=openhuman_config)
    route_request.input.metadata = {"action": "send_email"}
    response = await adapter.complete(route_request)
    assert response.output.type.value == "error"
    assert "not allowed in read-only mode" in response.output.content


@pytest.mark.asyncio
async def test_openhuman_write_action_blocked(openhuman_config, route_request):
    """Test that write actions are always blocked by policy."""
    openhuman_config["default_mode"] = "full"
    adapter = OpenHumanAdapter(cfg=openhuman_config)
    route_request.input.metadata = {"action": "delete_files"}
    response = await adapter.complete(route_request)
    assert response.output.type.value == "error"
    assert "forbidden" in response.output.content.lower()


@pytest.mark.asyncio
async def test_openhuman_action_inference_from_task_type(openhuman_config):
    """Test action inference from task type."""
    adapter = OpenHumanAdapter(cfg=openhuman_config)

    request_research = RouteRequest(
        request_id="test-1",
        task_id="task-1",
        task_type=TaskType.RESEARCH,
        objective="Research something",
        input=RouteInput(messages=[], metadata={}),
        constraints=RouteConstraints(),
    )

    action = adapter._action_from_request(request_research)
    assert action == "context_query"

    request_personal = RouteRequest(
        request_id="test-2",
        task_id="task-2",
        task_type=TaskType.PERSONAL_CONTEXT,
        objective="Get personal context",
        input=RouteInput(messages=[], metadata={}),
        constraints=RouteConstraints(),
    )

    action = adapter._action_from_request(request_personal)
    assert action == "memory_search"


@pytest.mark.asyncio
async def test_openhuman_http_error_handling(openhuman_config, route_request):
    """Test handling of HTTP errors from sidecar."""
    adapter = OpenHumanAdapter(cfg=openhuman_config)

    # Mock the HTTP response
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_http_response = AsyncMock()
        mock_http_response.status_code = 503
        mock_http_response.text = "Service unavailable"
        mock_client.post.return_value = mock_http_response

        response = await adapter.complete(route_request)

        assert response.output.type.value == "error"
        assert "503" in response.output.content
        assert response.route_reason == "openhuman_http_error"


@pytest.mark.asyncio
async def test_openhuman_exception_handling(openhuman_config, route_request):
    """Test exception handling during sidecar call."""
    adapter = OpenHumanAdapter(cfg=openhuman_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.post.side_effect = ConnectionError("Cannot reach sidecar")

        response = await adapter.complete(route_request)

        assert response.output.type.value == "error"
        assert "Cannot reach sidecar" in response.output.content
        assert response.route_reason == "openhuman_exception"


@pytest.mark.asyncio
async def test_openhuman_health_check(openhuman_config):
    """Test health check endpoint."""
    adapter = OpenHumanAdapter(cfg=openhuman_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_http_response = AsyncMock()
        mock_http_response.status_code = 200
        mock_client.get.return_value = mock_http_response

        health = await adapter.health()

        assert health.reachable is True


@pytest.mark.asyncio
async def test_openhuman_health_check_unreachable(openhuman_config):
    """Test health check when sidecar is unreachable."""
    adapter = OpenHumanAdapter(cfg=openhuman_config)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = ConnectionError("Connection refused")

        health = await adapter.health()

        assert health.reachable is False
        assert "Connection refused" in health.error


@pytest.mark.asyncio
async def test_openhuman_success_response(openhuman_config, route_request):
    """Test successful completion response from OpenHuman."""
    adapter = OpenHumanAdapter(cfg=openhuman_config)
    route_request.input.metadata = {"action": "context_query"}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_http_response = AsyncMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = {
            "context": [{"scope": "research", "summary": "Found relevant info"}]
        }
        mock_client.post.return_value = mock_http_response

        response = await adapter.complete(route_request)

        assert response.output.type.value == "text"
        assert response.route_reason == "openhuman_ok"
        assert response.selected_provider == "openhuman"
