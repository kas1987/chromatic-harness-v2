"""Adapter for remote Ollama (e.g., desktop over LAN)."""

import json
import urllib.request

from ..contracts import (
    RouteRequest,
    RouteResponse,
    RouteOutput,
    OutputType,
    RouteUsage,
)
from ..adapters.base import BaseAdapter, AdapterHealth


class OllamaRemoteAdapter(BaseAdapter):
    """Reach Ollama on a remote machine (desktop with GPU) over LAN.

    Expects cfg:
        - host (str): e.g. "desktop.local"
        - port (int): e.g. 11434
        - model (str): e.g. "llama3.1:8b"
        - enabled (bool)
    """

    def __init__(self, name: str, cfg: dict):
        super().__init__(name, cfg)
        self.host = cfg.get("host", "localhost")
        self.port = cfg.get("port", 11434)
        self.model = cfg.get("model", "")
        self.timeout_s = cfg.get("timeout_s", 10)

    def _url(self, path: str) -> str:
        return f"http://{self.host}:{self.port}{path}"

    async def health(self) -> AdapterHealth:
        try:
            req = urllib.request.Request(
                self._url("/api/tags"), method="GET"
            )
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                if resp.status == 200:
                    return AdapterHealth(reachable=True, latency_ms=100)
                return AdapterHealth(reachable=False, latency_ms=0, error=f"status {resp.status}")
        except Exception as exc:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(exc)[:200])

    async def complete(self, req: RouteRequest) -> RouteResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": req.objective}],
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        try:
            request = urllib.request.Request(
                self._url("/api/chat"),
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout_s * 3) as resp:
                result = json.loads(resp.read())
                content = result.get("message", {}).get("content", "")
                return RouteResponse(
                    request_id=req.request_id,
                    selected_provider=self.name,
                    selected_model=self.model,
                    output=RouteOutput(type=OutputType.TEXT, content=content),
                    usage=RouteUsage(),
                )
        except Exception as exc:
            return self.normalize_error(req.request_id, f"OllamaRemote failed: {exc}")
