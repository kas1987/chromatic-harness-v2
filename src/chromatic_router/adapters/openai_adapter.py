"""OpenAI cloud adapter stub."""
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


class OpenAIAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {
            "enabled": bool(os.environ.get("OPENAI_API_KEY")),
            "env_key": "OPENAI_API_KEY",
        }
        super().__init__("openai", cfg)

    async def health(self) -> AdapterHealth:
        return AdapterHealth(
            reachable=bool(os.environ.get(self.cfg.get("env_key", "OPENAI_API_KEY"))),
            latency_ms=0,
            error="" if self.enabled else "OPENAI_API_KEY not set",
        )

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        logs.warnings.append(
            "OpenAIAdapter.complete() is a stub — wire openai SDK when ready."
        )
        return RouteResponse(
            request_id=req.request_id,
            selected_provider=self.name,
            route_reason="openai_stub",
            output=RouteOutput(
                type=OutputType.TEXT, content="[OpenAI stub — not yet wired]"
            ),
            logs=logs,
        )
