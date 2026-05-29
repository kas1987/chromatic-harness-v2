"""OpenRouter broker adapter — routes to 200+ models."""

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


class OpenRouterAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = dict(cfg) if cfg else {}
        env_key = cfg.get("env_key", "OPENROUTER_API_KEY")
        cfg["enabled"] = bool(os.environ.get(env_key))
        cfg.setdefault("env_key", "OPENROUTER_API_KEY")
        cfg.setdefault("model", "openrouter/auto")
        cfg.setdefault("timeout", 60)
        super().__init__("openrouter", cfg)
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.cfg.get("timeout", 60),
                headers={
                    "Authorization": f"Bearer {os.environ.get(self.cfg.get('env_key', 'OPENROUTER_API_KEY'))}",
                    "HTTP-Referer": "https://github.com/kas1987/chromatic-harness-v2",
                    "X-Title": "Chromatic Harness v2",
                },
            )
        return self._client

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(
                reachable=False,
                latency_ms=0,
                error="OPENROUTER_API_KEY not set",
            )
        try:
            client = self._get_client()
            start = time.time()
            resp = await client.get("https://openrouter.ai/api/v1/models")
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
                    req.request_id, "OPENROUTER_API_KEY not configured"
                )

            client = self._get_client()
            start = time.time()

            messages = (
                req.input.messages
                if req.input.messages
                else [{"role": "user", "content": req.objective}]
            )
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json={
                    "model": self.cfg.get("model", "openrouter/auto"),
                    "messages": messages,
                    "max_tokens": req.constraints.max_tokens or 2048,
                    "temperature": 0.7,
                },
            )

            latency_ms = int((time.time() - start) * 1000)
            if response.status_code != 200:
                return self.normalize_error(
                    req.request_id, f"OpenRouter status {response.status_code}"
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
            logs.errors.append(f"OpenRouter error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
