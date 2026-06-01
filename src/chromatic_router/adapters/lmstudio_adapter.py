"""LM Studio local adapter stub.

Implements the BaseAdapter contract. Will connect to LM Studio's
OpenAI-compatible local server at http://localhost:1234/v1.
"""
# ruff: noqa: E402

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from router.adapters.base import BaseAdapter, AdapterHealth  # noqa: E402
from router.contracts import (
    RouteRequest,
    RouteResponse,
    OutputType,
    RouteOutput,
    RouteLogs,
)  # noqa: E402


class LMStudioAdapter(BaseAdapter):
    """Local LM Studio adapter."""

    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {
            "enabled": os.environ.get("LMSTUDIO_ENABLED", "true").lower() == "true",
            "base_url": os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
        }
        super().__init__("lmstudio", cfg)
        self.base_url = self.cfg.get("base_url", "http://localhost:1234/v1").rstrip("/")

    async def health(self) -> AdapterHealth:
        import httpx
        import time

        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.base_url}/models", timeout=5.0)
            latency = int((time.perf_counter() - t0) * 1000)
            ok = r.status_code == 200
            return AdapterHealth(
                reachable=ok,
                latency_ms=latency,
                error="" if ok else f"status={r.status_code}",
            )
        except Exception as exc:
            latency = int((time.perf_counter() - t0) * 1000)
            return AdapterHealth(reachable=False, latency_ms=latency, error=str(exc))

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        logs.warnings.append("LMStudioAdapter.complete() is a stub — wire OpenAI-compatible client when ready.")
        return RouteResponse(
            request_id=req.request_id,
            selected_provider=self.name,
            route_reason="lmstudio_stub",
            output=RouteOutput(type=OutputType.TEXT, content="[LM Studio stub — not yet wired]"),
            logs=logs,
        )
