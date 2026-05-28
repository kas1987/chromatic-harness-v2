"""Featherless broker adapter — cost-optimized inference."""

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


class FeatherlessAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {
            "enabled": bool(os.environ.get("FEATHERLESS_API_KEY")),
            "env_key": "FEATHERLESS_API_KEY",
            "model": "meta-llama/Llama-3.1-8B-Instruct",
            "timeout": 60,
        }
        super().__init__("featherless", cfg)
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.cfg.get("timeout", 60),
                headers={
                    "Authorization": f"Bearer {os.environ.get(self.cfg.get('env_key', 'FEATHERLESS_API_KEY'))}",
                },
            )
        return self._client

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(
                reachable=False,
                latency_ms=0,
                error="FEATHERLESS_API_KEY not set",
            )
        try:
            client = self._get_client()
            start = time.time()
            resp = await client.get("https://api.featherless.ai/v1/models")
            latency_ms = int((time.time() - start) * 1000)
            return AdapterHealth(
                reachable=resp.status_code == 200, latency_ms=latency_ms
            )
        except Exception as e:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(e))

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        try:
            if not self.enabled:
                return self.normalize_error(
                    req.request_id, "FEATHERLESS_API_KEY not configured"
                )

            client = self._get_client()
            start = time.time()

            response = await client.post(
                "https://api.featherless.ai/v1/chat/completions",
                json={
                    "model": self.cfg.get("model", "meta-llama/Llama-3.1-8B-Instruct"),
                    "messages": [{"role": "user", "content": req.prompt}],
                    "max_tokens": req.constraints.max_tokens or 2048,
                    "temperature": req.constraints.temperature or 0.7,
                },
            )

            latency_ms = int((time.time() - start) * 1000)
            if response.status_code != 200:
                return self.normalize_error(
                    req.request_id, f"Featherless status {response.status_code}"
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.TEXT, content=content),
                usage=RouteUsage(
                    input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                    output_tokens=data.get("usage", {}).get("completion_tokens", 0),
                    total_tokens=data.get("usage", {}).get("total_tokens", 0),
                ),
                latency_ms=latency_ms,
                logs=logs,
            )
        except Exception as e:
            logs.errors.append(f"Featherless error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
