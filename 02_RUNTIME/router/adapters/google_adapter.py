"""Google Gemini adapter stub."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .base import BaseAdapter, AdapterHealth
from ..contracts import RouteRequest, RouteResponse, OutputType, RouteOutput, RouteUsage, RouteLogs


class GoogleAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {
            "enabled": bool(os.environ.get("GOOGLE_API_KEY")),
            "env_key": "GOOGLE_API_KEY",
        }
        super().__init__("google", cfg)

    async def health(self) -> AdapterHealth:
        return AdapterHealth(
            reachable=bool(os.environ.get(self.cfg.get("env_key", "GOOGLE_API_KEY"))),
            latency_ms=0,
            error="" if self.enabled else "GOOGLE_API_KEY not set",
        )

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        logs.warnings.append("GoogleAdapter.complete() is a stub — wire google.generativeai SDK when ready.")
        return RouteResponse(
            request_id=req.request_id,
            selected_provider=self.name,
            route_reason="google_stub",
            output=RouteOutput(type=OutputType.TEXT, content="[Google stub — not yet wired]"),
            logs=logs,
        )
