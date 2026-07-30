"""Router auto-path robustness tests.

Regression coverage for routing fallback behavior:
1. An adapter returning an ERROR RouteResponse (not raising) must not break the
   fallback loop — a broken provider (e.g. native_claude with no working CLI)
   must hand off to a reachable one.
2. Logical provider names emitted by the routing table (ollama_local) must be
   first-class providers in providers.yaml so the adapter factory creates a
   dedicated adapter and the privacy allowlist admits them. Runtime alias
   remapping inside router.py has been removed.

Uses fake adapters so nothing touches the network.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "02_RUNTIME"))

from router.router import ChromaticRouter  # noqa: E402
from router.contracts import (  # noqa: E402
    RouteRequest,
    RouteInput,
    RouteConstraints,
    RouteConfidence,
    RouteResponse,
    RouteOutput,
    OutputType,
    TaskType,
    PrivacyClass,
    ConfidenceBand,
)
from router.adapters.base import BaseAdapter, AdapterHealth  # noqa: E402


class _FakeAdapter(BaseAdapter):
    def __init__(self, name: str, *, mode: str):
        super().__init__(name, {"enabled": True})
        self.mode = mode  # "ok" | "error" | "raise"
        self.calls = 0

    async def complete(self, req: RouteRequest) -> RouteResponse:
        self.calls += 1
        if self.mode == "raise":
            raise RuntimeError(f"{self.name} blew up")
        if self.mode == "error":
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.ERROR, content="simulated failure"),
            )
        return RouteResponse(
            request_id=req.request_id,
            selected_provider=self.name,
            output=RouteOutput(type=OutputType.TEXT, content=f"ok from {self.name}"),
        )

    async def health(self) -> AdapterHealth:  # pragma: no cover
        return AdapterHealth(reachable=True, latency_ms=1)


def _req(prefer: str) -> RouteRequest:
    return RouteRequest(
        request_id="t-1",
        task_id="t",
        task_type=TaskType.CLASSIFICATION,
        objective="do a thing",
        input=RouteInput(messages=[{"role": "user", "content": "do a thing"}]),
        constraints=RouteConstraints(privacy_class=PrivacyClass.P0, allow_cloud=True),
        confidence=RouteConfidence(score=95.0, band=ConfidenceBand.VERY_HIGH),
        preferred_provider=prefer,
    )


def _router_with(adapters: dict) -> ChromaticRouter:
    return ChromaticRouter(adapters=adapters)


def test_error_response_falls_through_to_next_provider():
    broken = _FakeAdapter("native_claude", mode="error")
    good = _FakeAdapter("ollama", mode="ok")
    router = _router_with({"native_claude": broken, "ollama": good})
    req = _req("native_claude")
    req.fallback_chain = ["ollama"]
    resp = asyncio.run(router.route(req))
    assert resp.output.type == OutputType.TEXT
    assert resp.selected_provider == "ollama"
    assert good.calls == 1


def test_raised_exception_falls_through():
    boom = _FakeAdapter("native_claude", mode="raise")
    good = _FakeAdapter("ollama", mode="ok")
    router = _router_with({"native_claude": boom, "ollama": good})
    req = _req("native_claude")
    req.fallback_chain = ["ollama"]
    resp = asyncio.run(router.route(req))
    assert resp.output.type == OutputType.TEXT
    assert resp.selected_provider == "ollama"


def test_ollama_local_is_registered_logical_provider():
    # The routing table emits 'ollama_local'; providers.yaml now declares it as
    # a first-class logical provider, so the adapter factory creates an adapter
    # with that exact name and the privacy allowlist admits it.
    good = _FakeAdapter("ollama_local", mode="ok")
    router = _router_with({"ollama_local": good})
    assert router._resolve_adapter_name("ollama_local") == "ollama_local"
    assert router._provider_is_available("ollama_local") is True


def test_ollama_local_routes_through_logical_adapter():
    good = _FakeAdapter("ollama_local", mode="ok")
    router = _router_with({"ollama_local": good})
    resp = asyncio.run(router.route(_req("ollama_local")))
    assert resp.output.type == OutputType.TEXT
    assert good.calls == 1


def test_all_error_responses_surface_error_when_no_mock():
    a = _FakeAdapter("native_claude", mode="error")
    b = _FakeAdapter("ollama", mode="error")
    router = _router_with({"native_claude": a, "ollama": b})  # no mock
    req = _req("native_claude")
    req.fallback_chain = ["ollama"]
    resp = asyncio.run(router.route(req))
    assert resp.output.type == OutputType.ERROR


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
