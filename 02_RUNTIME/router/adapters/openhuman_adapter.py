"""OpenHuman sidecar adapter — read-only by default, fails closed."""

import os
import time
from typing import Any

import httpx

from .base import BaseAdapter, AdapterHealth
from ..contracts import (
    RouteRequest,
    RouteResponse,
    OutputType,
    RouteOutput,
    RouteUsage,
    RouteLogs,
)


class OpenHumanAdapter(BaseAdapter):
    """
    Phase-1 sidecar adapter.
    - Disabled by default.
    - Read-only: only health, memory_search, context_query allowed.
    - All write actions are rejected locally before reaching the sidecar.
    """

    READONLY_ACTIONS = {"health_check", "memory_search", "context_query"}
    WRITE_ACTIONS = {
        "send_email",
        "modify_calendar",
        "mutate_github",
        "delete_files",
        "write_chromatic_memory",
    }

    def __init__(self, cfg: dict[str, Any] | None = None):
        # Load from env if no cfg passed
        if cfg is None:
            cfg = {
                "enabled": os.environ.get("OPENHUMAN_ENABLED", "false").lower() == "true",
                "base_url": os.environ.get("OPENHUMAN_BASE_URL", "http://127.0.0.1:8787"),
                "env_key": "OPENHUMAN_BEARER_TOKEN",
                "privacy_max": "P2",
                "default_mode": "read_only",
            }
        super().__init__("openhuman", cfg)
        self.base_url = self.cfg.get("base_url", "http://127.0.0.1:8787").rstrip("/")
        token = os.environ.get(self.cfg.get("env_key", "OPENHUMAN_BEARER_TOKEN"), "")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.mode = self.cfg.get("default_mode", "read_only")

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(reachable=False, latency_ms=0, error="disabled_by_config")
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{self.base_url}/health", headers=self.headers, timeout=5.0
                )
            latency = int((time.perf_counter() - t0) * 1000)
            ok = r.status_code == 200
            return AdapterHealth(
                reachable=ok, latency_ms=latency, error="" if ok else f"status={r.status_code}"
            )
        except Exception as exc:
            latency = int((time.perf_counter() - t0) * 1000)
            return AdapterHealth(reachable=False, latency_ms=latency, error=str(exc))

    def _action_from_request(self, req: RouteRequest) -> str:
        """Derive intended action from task_type and metadata."""
        meta = req.input.metadata or {}
        action = meta.get("action", "")
        if action:
            return action
        mapping = {
            "personal_context": "memory_search",
            "research": "context_query",
            "classification": "context_query",
        }
        return mapping.get(req.task_type.value, "context_query")

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        if not self.enabled:
            logs.errors.append("OpenHuman is disabled by config (OPENHUMAN_ENABLED=false).")
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                route_reason="openhuman_disabled",
                output=RouteOutput(type=OutputType.ERROR, content="OpenHuman disabled."),
                logs=logs,
            )

        action = self._action_from_request(req)

        # Phase-1 read-only enforcement
        if self.mode == "read_only" and action not in self.READONLY_ACTIONS:
            logs.errors.append(
                f"OpenHuman action '{action}' blocked in read-only mode."
            )
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                route_reason="openhuman_readonly_blocked",
                output=RouteOutput(
                    type=OutputType.ERROR,
                    content=f"Action '{action}' is not allowed in read-only mode.",
                ),
                logs=logs,
            )

        if action in self.WRITE_ACTIONS:
            logs.errors.append(
                f"OpenHuman write action '{action}' blocked by policy."
            )
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                route_reason="openhuman_write_blocked",
                output=RouteOutput(
                    type=OutputType.ERROR,
                    content=f"Write action '{action}' is forbidden.",
                ),
                logs=logs,
            )

        # Actual sidecar call
        t0 = time.perf_counter()
        try:
            payload = {
                "action": action,
                "objective": req.objective,
                "context": req.input.messages,
            }
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{self.base_url}/api/v1/query",
                    headers={**self.headers, "Content-Type": "application/json"},
                    json=payload,
                    timeout=30.0,
                )
            latency = int((time.perf_counter() - t0) * 1000)
            if r.status_code != 200:
                logs.errors.append(f"OpenHuman returned {r.status_code}: {r.text[:200]}")
                return RouteResponse(
                    request_id=req.request_id,
                    selected_provider=self.name,
                    route_reason="openhuman_http_error",
                    output=RouteOutput(
                        type=OutputType.ERROR,
                        content=f"OpenHuman error {r.status_code}",
                    ),
                    logs=logs,
                )
            data = r.json()
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                selected_model="openhuman-sidecar",
                route_reason="openhuman_ok",
                latency_ms=latency,
                output=RouteOutput(
                    type=OutputType.JSON if isinstance(data, dict) else OutputType.TEXT,
                    content=str(data) if not isinstance(data, str) else data,
                ),
                usage=RouteUsage(),
                logs=logs,
            )
        except Exception as exc:
            latency = int((time.perf_counter() - t0) * 1000)
            logs.errors.append(f"OpenHuman exception: {exc}")
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                route_reason="openhuman_exception",
                output=RouteOutput(type=OutputType.ERROR, content=str(exc)),
                latency_ms=latency,
                logs=logs,
            )
