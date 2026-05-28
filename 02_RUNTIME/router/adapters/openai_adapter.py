"""OpenAI cloud adapter — GPT-4, GPT-3.5."""

from __future__ import annotations

import os
import time
from typing import Any

from .base import BaseAdapter, AdapterHealth
from ..contracts import (
    RouteRequest,
    RouteResponse,
    OutputType,
    RouteOutput,
    RouteUsage,
    RouteLogs,
)


class OpenAIAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {
            "enabled": bool(os.environ.get("OPENAI_API_KEY")),
            "env_key": "OPENAI_API_KEY",
            "model": "gpt-4o-mini",
            "timeout": 30,
        }
        super().__init__("openai", cfg)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=os.environ.get(self.cfg.get("env_key", "OPENAI_API_KEY"))
                )
            except ImportError:
                raise RuntimeError("openai SDK not installed: pip install openai")
        return self._client

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(
                reachable=False,
                latency_ms=0,
                error="OPENAI_API_KEY not set",
            )
        try:
            start = time.time()
            client = self._get_client()
            await client.models.list()
            latency_ms = int((time.time() - start) * 1000)
            return AdapterHealth(reachable=True, latency_ms=latency_ms)
        except Exception as e:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(e))

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        try:
            if not self.enabled:
                return self.normalize_error(
                    req.request_id, "OPENAI_API_KEY not configured"
                )

            client = self._get_client()
            start = time.time()

            messages = (
                req.input.messages
                if req.input.messages
                else [{"role": "user", "content": req.objective}]
            )
            response = await client.chat.completions.create(
                model=self.cfg.get("model", "gpt-4o-mini"),
                messages=messages,
                max_tokens=req.constraints.max_tokens or 2048,
                temperature=0.7,
                timeout=self.cfg.get("timeout", 30),
            )

            latency_ms = int((time.time() - start) * 1000)
            content = response.choices[0].message.content

            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.TEXT, content=content),
                usage=RouteUsage(
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                ),
                latency_ms=latency_ms,
                logs=logs,
            )
        except Exception as e:
            logs.errors.append(f"OpenAI error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
