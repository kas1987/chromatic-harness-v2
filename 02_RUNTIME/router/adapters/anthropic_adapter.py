"""Anthropic Claude adapter — Claude 3.x series."""

from __future__ import annotations

import os
import time
from typing import Any

from .base import AdapterError, BaseAdapter, AdapterHealth
import httpx
from ..contracts import (
    RouteRequest,
    RouteResponse,
    OutputType,
    RouteOutput,
    RouteUsage,
    RouteLogs,
)


class AnthropicAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = dict(cfg) if cfg else {}
        env_key = cfg.get("env_key", "ANTHROPIC_API_KEY")
        cfg["enabled"] = bool(os.environ.get(env_key))
        cfg.setdefault("env_key", "ANTHROPIC_API_KEY")
        cfg.setdefault("model", "claude-3-5-sonnet-20241022")
        cfg.setdefault("timeout", 30)
        super().__init__("anthropic", cfg)
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(
                    api_key=os.environ.get(self.cfg.get("env_key", "ANTHROPIC_API_KEY"))  # pragma: allowlist secret
                )
            except ImportError as exc:
                raise AdapterError("anthropic SDK not installed: pip install anthropic", provider="anthropic") from exc
        return self._client

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(
                reachable=False,
                latency_ms=0,
                error="ANTHROPIC_API_KEY not set",
            )
        try:
            start = time.time()
            client = self._get_client()
            await client.messages.count_tokens(
                model=self.cfg.get("model", "claude-3-5-sonnet-20241022"),
                messages=[{"role": "user", "content": "test"}],
            )
            latency_ms = int((time.time() - start) * 1000)
            return AdapterHealth(reachable=True, latency_ms=latency_ms)
        except Exception as e:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(e))

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        try:
            if not self.enabled:
                return self.normalize_error(req.request_id, "ANTHROPIC_API_KEY not configured")

            client = self._get_client()
            start = time.time()

            messages = req.input.messages if req.input.messages else [{"role": "user", "content": req.objective}]
            response = await client.messages.create(
                model=self.cfg.get("model", "claude-3-5-sonnet-20241022"),
                max_tokens=req.constraints.max_tokens or 2048,
                messages=messages,
                timeout=self.cfg.get("timeout", 30),
            )

            latency_ms = int((time.time() - start) * 1000)
            content = response.content[0].text

            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.TEXT, content=content),
                usage=RouteUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                ),
                latency_ms=latency_ms,
                logs=logs,
            )
        except Exception as e:
            logs.errors.append(f"Anthropic error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
