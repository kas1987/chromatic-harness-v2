"""OmniRoute local free-tier gateway adapter.

OmniRoute exposes an OpenAI-compatible endpoint at http://localhost:20128/v1
and routes across free/pooled providers. No real API key is required for the
default local install (REQUIRE_API_KEY=false);  # pragma: allowlist secret
we send a dummy key that can be overridden via OMNIROUTE_API_KEY.
"""

from __future__ import annotations

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


class OmniRouteAdapter(BaseAdapter):
    """OpenAI-compatible adapter for the local OmniRoute gateway.

    Treats OmniRoute as a free local gateway: it runs on localhost, consumes no
    paid CHV2 budget, but still egresses to third-party free clouds. The harness
    privacy gate therefore classifies it as a broker/cloud for P-class filtering
    (P4/P5 hard block; P3 human gate) even though billing_axis.py books it as
    Axis F (free local).
    """

    DEFAULT_BASE_URL = "http://localhost:20128/v1"
    DEFAULT_MODEL = "oc/deepseek-v4-flash-free"
    DUMMY_KEY = "not-needed"  # noqa: S105  # pragma: allowlist secret

    def __init__(self, cfg: dict[str, Any] | None = None):
        cfg = dict(cfg) if cfg else {}
        env_key = cfg.get("env_key", "OMNIROUTE_API_KEY")
        cfg.setdefault("env_key", "OMNIROUTE_API_KEY")
        cfg.setdefault("base_url", self.DEFAULT_BASE_URL)
        cfg.setdefault("model", self.DEFAULT_MODEL)
        cfg.setdefault("timeout", 60)
        # OmniRoute is enabled when the gateway base URL is configured. A real key
        # is optional for the default local setup.
        cfg["enabled"] = cfg.get("enabled", True) and bool(cfg.get("base_url"))
        super().__init__("omniroute", cfg)
        self._client: httpx.AsyncClient | None = None

    def _api_key(self) -> str:
        return os.environ.get(self.cfg.get("env_key", "OMNIROUTE_API_KEY")) or self.DUMMY_KEY

    def _base_url(self) -> str:
        return str(self.cfg.get("base_url", self.DEFAULT_BASE_URL)).rstrip("/")

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.cfg.get("timeout", 60),
                headers={
                    # pragma: allowlist secret
                    "Authorization": f"Bearer {self._api_key()}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(
                reachable=False,
                latency_ms=0,
                error="OmniRoute adapter disabled (no base_url)",
            )
        try:
            client = self._get_client()
            start = time.time()
            resp = await client.get(f"{self._base_url()}/models")
            latency_ms = int((time.time() - start) * 1000)
            return AdapterHealth(reachable=resp.status_code == 200, latency_ms=latency_ms)
        except Exception as e:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(e))

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        try:
            if not self.enabled:
                return self.normalize_error(req.request_id, "OmniRoute adapter disabled")

            client = self._get_client()
            start = time.time()

            messages = req.input.messages if req.input.messages else [{"role": "user", "content": req.objective}]
            model = self.cfg.get("model", self.DEFAULT_MODEL)
            response = await client.post(
                f"{self._base_url()}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": req.constraints.max_tokens or 2048,
                    "temperature": 0.7,
                },
            )

            latency_ms = int((time.time() - start) * 1000)
            if response.status_code != 200:
                return self.normalize_error(req.request_id, f"OmniRoute status {response.status_code}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                selected_model=model,
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
            logs.errors.append(f"OmniRoute error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
