"""Google Gemini adapter — uses google-genai SDK (v1+)."""

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

_DEFAULT_MODEL = "gemini-2.0-flash"


class GoogleAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = dict(cfg) if cfg else {}
        api_key = os.environ.get(cfg.get("env_key", "GOOGLE_API_KEY"), "")
        cfg.setdefault("enabled", bool(api_key))
        cfg.setdefault("env_key", "GOOGLE_API_KEY")
        cfg.setdefault("model", _DEFAULT_MODEL)
        cfg.setdefault("timeout", 30)
        super().__init__("google", cfg)
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google import genai

                api_key = os.environ.get(self.cfg.get("env_key", "GOOGLE_API_KEY"))
                self._client = genai.Client(api_key=api_key)
            except ImportError:
                raise RuntimeError(
                    "google-genai not installed: pip install google-genai"
                )
        return self._client

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(
                reachable=False, latency_ms=0, error="GOOGLE_API_KEY not set"
            )
        try:
            start = time.time()
            client = self._get_client()
            # Lightweight check — list first model
            next(iter(client.models.list()), None)
            return AdapterHealth(
                reachable=True, latency_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(e)[:200])

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        if not self.enabled:
            return self.normalize_error(req.request_id, "GOOGLE_API_KEY not configured")
        try:
            client = self._get_client()
            prompt = (
                "\n".join(m.get("content", "") for m in req.input.messages)
                if req.input.messages
                else req.objective
            )
            model = self.cfg.get("model", _DEFAULT_MODEL)
            start = time.time()
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            latency_ms = int((time.time() - start) * 1000)
            # Re-raise rate limit / quota errors so the router falls back
            if hasattr(response, "prompt_feedback") and getattr(
                response.prompt_feedback, "block_reason", None
            ):
                raise RuntimeError(f"Blocked: {response.prompt_feedback.block_reason}")
            content = response.text or ""
            if not content:
                raise RuntimeError("Empty response from Gemini")
            usage = getattr(response, "usage_metadata", None)
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.TEXT, content=content),
                usage=RouteUsage(
                    input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                    output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                    total_tokens=getattr(usage, "total_token_count", 0) or 0,
                ),
                latency_ms=latency_ms,
                logs=logs,
            )
        except Exception as e:
            logs.errors.append(f"Google error: {e}")
            return self.normalize_error(req.request_id, str(e)[:300])
