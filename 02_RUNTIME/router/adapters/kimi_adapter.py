"""Kimi (Moonshot AI) broker adapter — long-context builder/scout model."""

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

_BASE_URL = "https://api.moonshot.cn/v1"
_DEFAULT_MODEL = "moonshot-v1-32k"


class KimiAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = dict(cfg) if cfg else {}
        env_key = cfg.get("env_key", "MOONSHOT_API_KEY")
        cfg["enabled"] = bool(os.environ.get(env_key))
        cfg.setdefault("env_key", "MOONSHOT_API_KEY")
        cfg.setdefault("base_url", _BASE_URL)
        cfg.setdefault("model", _DEFAULT_MODEL)
        cfg.setdefault("timeout", 90)
        super().__init__("kimi", cfg)
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.cfg.get("timeout", 90),
                headers={
                    "Authorization": f"Bearer {os.environ.get(self.cfg.get('env_key', 'MOONSHOT_API_KEY'), '')}",
                },
            )
        return self._client

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(
                reachable=False, latency_ms=0, error="MOONSHOT_API_KEY not set"
            )
        try:
            client = self._get_client()
            start = time.time()
            resp = await client.get(f"{self.cfg.get('base_url', _BASE_URL)}/models")
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
                    req.request_id, "MOONSHOT_API_KEY not configured"
                )

            client = self._get_client()
            start = time.time()
            messages = (
                req.input.messages
                if req.input.messages
                else [{"role": "user", "content": req.objective}]
            )
            base_url = self.cfg.get("base_url", _BASE_URL)
            response = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": self.cfg.get("model", _DEFAULT_MODEL),
                    "messages": messages,
                    "max_tokens": req.constraints.max_tokens or 4096,
                    "temperature": 0.3,
                },
            )
            latency_ms = int((time.time() - start) * 1000)
            if response.status_code != 200:
                return self.normalize_error(
                    req.request_id, f"Kimi status {response.status_code}"
                )

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                selected_model=self.cfg.get("model", _DEFAULT_MODEL),
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
            logs.errors.append(f"Kimi error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
