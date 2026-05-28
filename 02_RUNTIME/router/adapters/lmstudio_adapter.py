"""LMStudio local adapter — local inference server."""

from __future__ import annotations

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


class LMStudioAdapter(BaseAdapter):
    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {
            "enabled": True,
            "host": "localhost",
            "port": 1234,
            "model": "local-model",
            "timeout": 60,
        }
        super().__init__("lmstudio", cfg)
        self._client = None

    def _url(self, path: str) -> str:
        host = self.cfg.get("host", "localhost")
        port = self.cfg.get("port", 1234)
        return f"http://{host}:{port}{path}"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.cfg.get("timeout", 60))
        return self._client

    async def health(self) -> AdapterHealth:
        try:
            client = self._get_client()
            start = time.time()
            resp = await client.get(self._url("/v1/models"))
            latency_ms = int((time.time() - start) * 1000)
            return AdapterHealth(
                reachable=resp.status_code == 200, latency_ms=latency_ms
            )
        except Exception as e:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(e))

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        try:
            client = self._get_client()
            start = time.time()

            messages = (
                req.input.messages
                if req.input.messages
                else [{"role": "user", "content": req.objective}]
            )
            response = await client.post(
                self._url("/v1/chat/completions"),
                json={
                    "model": self.cfg.get("model", "local-model"),
                    "messages": messages,
                    "max_tokens": req.constraints.max_tokens or 2048,
                    "temperature": 0.7,
                },
            )

            latency_ms = int((time.time() - start) * 1000)
            if response.status_code != 200:
                return self.normalize_error(
                    req.request_id, f"LMStudio status {response.status_code}"
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
            logs.errors.append(f"LMStudio error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
