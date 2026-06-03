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

_MAX_HISTORY_TURNS_DEFAULT = 20  # user+assistant pairs; system messages always kept


def _prune_messages(messages: list, max_turns: int) -> list:
    """Keep all system messages + the last max_turns user/assistant pairs.

    Prevents unbounded context growth in long RPI sessions where each call
    re-feeds the full accumulated history (observed: 14k→100k tokens in 71 calls).

    max_turns <= 0 means no pruning (keep all messages).
    """
    if not messages or max_turns <= 0:
        return messages
    system_msgs: list = []
    non_system: list = []
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "system":
            system_msgs.append(m)
        else:
            non_system.append(m)
    max_msg_count = max_turns * 2
    if len(non_system) > max_msg_count:
        non_system = non_system[-max_msg_count:]
    return system_msgs + non_system


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
        self.max_history_turns = cfg.get("max_history_turns", _MAX_HISTORY_TURNS_DEFAULT)
        self._client: httpx.AsyncClient | None = None

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

        raw_messages = (
            req.input.messages
            if req.input.messages
            else [{"role": "user", "content": req.objective}]
        )
        messages = _prune_messages(raw_messages, self.max_history_turns)
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
