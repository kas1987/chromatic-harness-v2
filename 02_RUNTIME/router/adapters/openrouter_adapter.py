"""OpenRouter broker adapter stub."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .base import BaseAdapter, AdapterHealth
from ..contracts import RouteRequest, RouteResponse, OutputType, RouteOutput, RouteUsage, RouteLogs


class OpenRouterAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {
            "enabled": bool(os.environ.get("OPENROUTER_API_KEY")),
            "env_key": "OPENROUTER_API_KEY",
        }
        super().__init__("openrouter", cfg)

    async def health(self) -> AdapterHealth:
        return AdapterHealth(
            reachable=bool(os.environ.get(self.cfg.get("env_key", "OPENROUTER_API_KEY"))),
            latency_ms=0,
            error="" if self.enabled else "OPENROUTER_API_KEY not set",
        )

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        logs.warnings.append("OpenRouterAdapter.complete() is a stub — wire openrouter SDK when ready.")
        return RouteResponse(
            request_id=req.request_id,
            selected_provider=self.name,
            route_reason="openrouter_stub",
            output=RouteOutput(type=OutputType.TEXT, content="[OpenRouter stub — not yet wired]"),
            logs=logs,
        )
