"""Mock adapter for testing and local fallback."""

import time
import uuid
from typing import Any

from .base import BaseAdapter, AdapterHealth
from ..contracts import RouteRequest, RouteResponse, OutputType, RouteOutput, RouteUsage


class MockAdapter(BaseAdapter):
    """Returns deterministic mock responses. Never calls external services."""

    def __init__(self, cfg: dict[str, Any] | None = None):
        super().__init__("mock", cfg or {"enabled": True})

    async def health(self) -> AdapterHealth:
        return AdapterHealth(reachable=True, latency_ms=1)

    async def complete(self, req: RouteRequest) -> RouteResponse:
        t0 = time.perf_counter()
        content = f"[mock] task={req.task_type.value} objective={req.objective[:80]}"
        latency = int((time.perf_counter() - t0) * 1000)
        return RouteResponse(
            request_id=req.request_id,
            selected_provider=self.name,
            selected_model="mock-v1",
            route_reason="mock_fallback",
            confidence_score=req.confidence.score,
            privacy_class=req.constraints.privacy_class,
            cost_estimate_usd=0.0,
            latency_ms=latency,
            output=RouteOutput(type=OutputType.TEXT, content=content),
            usage=RouteUsage(input_tokens=0, output_tokens=0, total_tokens=0),
        )
