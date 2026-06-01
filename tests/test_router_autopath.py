"""Router auto-path robustness tests.

Regression coverage for two bugs found 2026-05-31:
1. An adapter returning an ERROR RouteResponse (not raising) was treated as
   success and broke the fallback loop — so a broken provider (native_claude
   with no working CLI -> WinError 2) dead-ended instead of handing off to a
   reachable one.
2. The routing table / provider_selector use logical names (ollama_local) but
   the adapter is registered as 'ollama'; without an alias the auto-path picked
   a name with no adapter and the privacy gate (allowlist uses canonical names)
   dropped it, silently falling through to mock.

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


def test_ollama_local_alias_resolves_to_ollama_adapter():
    good = _FakeAdapter("ollama", mode="ok")
    router = _router_with({"ollama": good})
    # The routing table emits 'ollama_local'; the alias must map it to 'ollama'.
    assert router._resolve_adapter_name("ollama_local") == "ollama"
    assert router._provider_is_available("ollama_local") is True


def test_ollama_local_routes_through_alias():
    good = _FakeAdapter("ollama", mode="ok")
    router = _router_with({"ollama": good})
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
