"""Featherless broker adapter stub."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .base import BaseAdapter, AdapterHealth
from ..contracts import RouteRequest, RouteResponse, OutputType, RouteOutput, RouteUsage, RouteLogs


class FeatherlessAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {
            "enabled": bool(os.environ.get("FEATHERLESS_API_KEY")),
            "env_key": "FEATHERLESS_API_KEY",
        }
        super().__init__("featherless", cfg)

    async def health(self) -> AdapterHealth:
        return AdapterHealth(
            reachable=bool(os.environ.get(self.cfg.get("env_key", "FEATHERLESS_API_KEY"))),
            latency_ms=0,
            error="" if self.enabled else "FEATHERLESS_API_KEY not set",
        )

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        logs.warnings.append("FeatherlessAdapter.complete() is a stub — wire featherless client when ready.")
        return RouteResponse(
            request_id=req.request_id,
            selected_provider=self.name,
            route_reason="featherless_stub",
            output=RouteOutput(type=OutputType.TEXT, content="[Featherless stub — not yet wired]"),
            logs=logs,
        )
