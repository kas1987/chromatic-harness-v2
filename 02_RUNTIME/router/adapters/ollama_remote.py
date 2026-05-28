"""Adapter for remote Ollama (e.g., desktop over LAN)."""

import json
import time
from typing import Any

import httpx

from ..contracts import (
    RouteRequest,
    RouteResponse,
    RouteOutput,
    OutputType,
    RouteUsage,
    RouteLogs,
)
from ..adapters.base import BaseAdapter, AdapterHealth


class OllamaRemoteAdapter(BaseAdapter):
    """Reach Ollama on a remote machine (desktop with GPU) over LAN.

    Expects cfg:
        - host (str): e.g. "localhost"
        - port (int): e.g. 11434
        - model (str): e.g. "llama3.1:8b"
        - enabled (bool)
    """

    def __init__(self, name: str, cfg: dict):
        super().__init__(name, cfg)
        self.host = cfg.get("host", "localhost")
        self.port = cfg.get("port", 11434)
        self.model = cfg.get("model", "llama3.1:8b")
        self.timeout_s = cfg.get("timeout_s", 30)
        self._client = None

    def _url(self, path: str) -> str:
        return f"http://{self.host}:{self.port}{path}"

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_s)
        return self._client

    async def health(self) -> AdapterHealth:
        try:
            client = self._get_client()
            start = time.time()
            resp = await client.get(self._url("/api/tags"))
            latency_ms = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                return AdapterHealth(reachable=True, latency_ms=latency_ms)
            return AdapterHealth(
                reachable=False,
                latency_ms=latency_ms,
                error=f"status {resp.status_code}",
            )
        except Exception as e:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(e)[:200])

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        if not self.model:
            return self.normalize_error(req.request_id, "No Ollama model configured")

        messages = (
            req.input.messages
            if req.input.messages
            else [{"role": "user", "content": req.objective}]
        )
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        try:
            client = self._get_client()
            start = time.time()
            resp = await client.post(self._url("/api/chat"), json=payload)
            latency_ms = int((time.time() - start) * 1000)

            if resp.status_code != 200:
                return self.normalize_error(
                    req.request_id, f"Ollama status {resp.status_code}"
                )

            result = resp.json()
            content = result.get("message", {}).get("content", "")

            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.TEXT, content=content),
                latency_ms=latency_ms,
                logs=logs,
            )
        except Exception as e:
            logs.errors.append(f"Ollama error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
