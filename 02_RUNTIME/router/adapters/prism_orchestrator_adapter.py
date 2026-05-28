"""Prism Orchestrator adapter — cross-project routing to dual-entry dispatcher."""

from __future__ import annotations

import os
import time

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


class PrismOrchestratorAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = dict(cfg) if cfg else {}
        if "enabled" not in cfg:
            cfg["enabled"] = (
                os.environ.get("PRISM_ORCHESTRATOR_ENABLED", "false").lower() == "true"
            )
        if "base_url" not in cfg:
            cfg["base_url"] = os.environ.get(
                "PRISM_ORCHESTRATOR_URL", "http://127.0.0.1:8000"
            )
        cfg.setdefault("timeout", 60)
        super().__init__("prism-orchestrator", cfg)
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.cfg.get("timeout", 60))
        return self._client

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(
                reachable=False,
                latency_ms=0,
                error="PRISM_ORCHESTRATOR_ENABLED not set",
            )
        try:
            client = self._get_client()
            start = time.time()
            url = f"{self.cfg.get('base_url')}/health"
            resp = await client.get(url)
            latency_ms = int((time.time() - start) * 1000)
            return AdapterHealth(
                reachable=resp.status_code == 200, latency_ms=latency_ms
            )
        except Exception as e:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(e)[:200])

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        try:
            if not self.enabled:
                return self.normalize_error(
                    req.request_id, "PRISM_ORCHESTRATOR_ENABLED not set"
                )

            client = self._get_client()
            start = time.time()

            messages = (
                req.input.messages
                if req.input.messages
                else [{"role": "user", "content": req.objective}]
            )
            prompt = "\n".join([m.get("content", "") for m in messages])

            payload = {
                "prompt": prompt,
                "entrypoint": self.cfg.get("entrypoint", "ollama"),
                "metadata": {
                    "priority": "normal",
                    "task_type": req.task_type.value,
                    "request_id": req.request_id,
                    "max_tokens": req.constraints.max_tokens,
                },
            }

            url = f"{self.cfg.get('base_url')}/run"
            response = await client.post(url, json=payload)
            latency_ms = int((time.time() - start) * 1000)

            if response.status_code != 200:
                return self.normalize_error(
                    req.request_id,
                    f"Prism Orchestrator status {response.status_code}: {response.text[:200]}",
                )

            data = response.json()
            if not data.get("ok", True) and not data.get("output"):
                error_msg = (
                    data.get("error") or data.get("reason") or "Prism returned ok=false"
                )
                return self.normalize_error(req.request_id, f"Prism: {error_msg[:300]}")

            content = data.get("output") or ""

            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.TEXT, content=content),
                usage=RouteUsage(
                    input_tokens=len(prompt) // 4,
                    output_tokens=len(content) // 4,
                    total_tokens=(len(prompt) + len(content)) // 4,
                ),
                latency_ms=latency_ms,
                logs=logs,
            )
        except Exception as e:
            logs.errors.append(f"Prism Orchestrator error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
