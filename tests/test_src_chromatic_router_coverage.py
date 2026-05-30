"""Coverage-focused tests for canonical src.chromatic_router package."""

from __future__ import annotations

import asyncio

from chromatic_router import RouteRequest, TaskType
from chromatic_router.adapters.anthropic_adapter import AnthropicAdapter
from chromatic_router.adapters.featherless_adapter import FeatherlessAdapter
from chromatic_router.adapters.google_adapter import GoogleAdapter
from chromatic_router.adapters.lmstudio_adapter import LMStudioAdapter
from chromatic_router.adapters.ollama_adapter import OllamaAdapter
from chromatic_router.adapters.openai_adapter import OpenAIAdapter
from chromatic_router.adapters.openrouter_adapter import OpenRouterAdapter


def _req() -> RouteRequest:
    return RouteRequest(
        request_id="req-src-1",
        task_id="task-src-1",
        task_type=TaskType.CODING,
        objective="smoke",
    )


def test_cloud_stub_adapters_health_and_complete():
    adapters = [
        OpenAIAdapter({"enabled": True, "env_key": "OPENAI_API_KEY"}),
        OpenRouterAdapter({"enabled": True, "env_key": "OPENROUTER_API_KEY"}),
        AnthropicAdapter({"enabled": True, "env_key": "ANTHROPIC_API_KEY"}),
        GoogleAdapter({"enabled": True, "env_key": "GOOGLE_API_KEY"}),
        FeatherlessAdapter({"enabled": True, "env_key": "FEATHERLESS_API_KEY"}),
    ]

    for adapter in adapters:
        health = asyncio.run(adapter.health())
        assert health.latency_ms >= 0

        out = asyncio.run(adapter.complete(_req()))
        assert out.request_id == "req-src-1"
        assert out.selected_provider == adapter.name
        assert out.logs.warnings


def test_local_adapters_construct_and_complete():
    lm = LMStudioAdapter({"enabled": True, "base_url": "http://localhost:1234/v1"})
    lm_out = asyncio.run(lm.complete(_req()))
    assert lm_out.selected_provider == "lmstudio"

    ollama = OllamaAdapter({"enabled": True, "base_url": "http://localhost:11434"})
    assert ollama.name == "ollama"
