"""Google Gemini adapter — Gemini Pro."""

from __future__ import annotations

import os
import time

from .base import BaseAdapter, AdapterHealth
from ..contracts import (
    RouteRequest,
    RouteResponse,
    OutputType,
    RouteOutput,
    RouteUsage,
    RouteLogs,
)


class GoogleAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {
            "enabled": bool(os.environ.get("GOOGLE_API_KEY")),
            "env_key": "GOOGLE_API_KEY",
            "model": "gemini-pro",
            "timeout": 30,
        }
        super().__init__("google", cfg)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import google.generativeai as genai

                genai.configure(
                    api_key=os.environ.get(self.cfg.get("env_key", "GOOGLE_API_KEY"))
                )
                self._client = genai
            except ImportError:
                raise RuntimeError(
                    "google-generativeai SDK not installed: pip install google-generativeai"
                )
        return self._client

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(
                reachable=False,
                latency_ms=0,
                error="GOOGLE_API_KEY not set",
            )
        try:
            start = time.time()
            genai = self._get_client()
            genai.list_models()
            latency_ms = int((time.time() - start) * 1000)
            return AdapterHealth(reachable=True, latency_ms=latency_ms)
        except Exception as e:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(e))

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        try:
            if not self.enabled:
                return self.normalize_error(
                    req.request_id, "GOOGLE_API_KEY not configured"
                )

            genai = self._get_client()
            model = genai.GenerativeModel(self.cfg.get("model", "gemini-pro"))
            start = time.time()

            response = model.generate_content(
                req.prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=req.constraints.max_tokens or 2048,
                    temperature=req.constraints.temperature or 0.7,
                ),
            )

            latency_ms = int((time.time() - start) * 1000)
            content = response.text

            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.TEXT, content=content),
                latency_ms=latency_ms,
                logs=logs,
            )
        except Exception as e:
            logs.errors.append(f"Google error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
