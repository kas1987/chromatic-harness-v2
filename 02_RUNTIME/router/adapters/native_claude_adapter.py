"""Native Claude adapter — routes via claude CLI (subprocess or host relay)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
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

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_TIMEOUT = 120


class NativeClaudeAdapter(BaseAdapter):
    """
    Uses the `claude -p` CLI under the user's subscription.

    Two modes (auto-detected):
      relay  — POST to NATIVE_CLAUDE_RELAY_URL (host-side relay server).
               Used when running inside Docker where the CLI isn't available.
      subprocess — run `claude -p` directly (used when CLI is in PATH).
    """

    def __init__(self, cfg: dict | None = None):
        cfg = dict(cfg) if cfg else {}
        relay_url = os.environ.get("NATIVE_CLAUDE_RELAY_URL", "")
        has_cli = bool(shutil.which("claude"))
        cfg.setdefault("enabled", bool(relay_url) or has_cli)
        cfg.setdefault("relay_url", relay_url)
        cfg.setdefault("model", os.environ.get("NATIVE_CLAUDE_MODEL", _DEFAULT_MODEL))
        cfg.setdefault("timeout", _TIMEOUT)
        super().__init__("native_claude", cfg)
        self._http: httpx.AsyncClient | None = None

    def _use_relay(self) -> bool:
        return bool(self.cfg.get("relay_url"))

    def _http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.cfg.get("timeout", _TIMEOUT))
        return self._http

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(
                reachable=False,
                latency_ms=0,
                error="no relay URL and claude CLI not in PATH",
            )
        if self._use_relay():
            try:
                start = time.time()
                resp = await self._http_client().get(f"{self.cfg['relay_url']}/health")
                return AdapterHealth(
                    reachable=resp.status_code == 200,
                    latency_ms=int((time.time() - start) * 1000),
                )
            except Exception as e:
                return AdapterHealth(reachable=False, latency_ms=0, error=str(e)[:200])
        try:
            start = time.time()
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=5)
            return AdapterHealth(
                reachable=proc.returncode == 0,
                latency_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            return AdapterHealth(reachable=False, latency_ms=0, error=str(e)[:200])

    async def complete(self, req: RouteRequest) -> RouteResponse:
        logs = RouteLogs()
        if not self.enabled:
            return self.normalize_error(req.request_id, "native_claude not available")

        messages = (
            req.input.messages
            if req.input.messages
            else [{"role": "user", "content": req.objective}]
        )
        prompt = "\n".join(
            m.get("content", "") for m in messages if m.get("role") != "system"
        )
        system_parts = [
            m.get("content", "") for m in messages if m.get("role") == "system"
        ]
        model = self.cfg.get("model", _DEFAULT_MODEL)
        timeout = self.cfg.get("timeout", _TIMEOUT)

        if self._use_relay():
            return await self._complete_relay(  # type: ignore[return-value]
                req, prompt, system_parts, model, timeout, logs
            )
        return await self._complete_subprocess(  # type: ignore[return-value]
            req, prompt, system_parts, model, timeout, logs
        )

    async def _complete_relay(self, req, prompt, system_parts, model, timeout, logs):
        try:
            start = time.time()
            payload = {"prompt": prompt, "model": model}
            if system_parts:
                payload["system"] = " ".join(system_parts)
            resp = await self._http_client().post(
                f"{self.cfg['relay_url']}/complete", json=payload
            )
            latency_ms = int((time.time() - start) * 1000)
            if resp.status_code != 200:
                return self.normalize_error(
                    req.request_id, f"relay {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()
            content = data.get("result", "")
            usage = data.get("usage", {})
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.TEXT, content=content),
                usage=RouteUsage(
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("input_tokens", 0)
                    + usage.get("output_tokens", 0),
                ),
                latency_ms=latency_ms,
                logs=logs,
            )
        except Exception as e:
            logs.errors.append(f"native_claude relay error: {e}")
            return self.normalize_error(req.request_id, str(e)[:300])

    async def _complete_subprocess(
        self, req, prompt, system_parts, model, timeout, logs
    ):
        cmd = ["claude", "-p", prompt, "--output-format", "json", "--model", model]
        if system_parts:
            cmd += ["--system-prompt", " ".join(system_parts)]
        try:
            start = time.time()
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            latency_ms = int((time.time() - start) * 1000)
            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace")[:300]
                return self.normalize_error(
                    req.request_id, f"claude CLI exit {proc.returncode}: {err}"
                )
            data = json.loads(stdout.decode("utf-8", errors="replace"))
            if data.get("is_error") or data.get("subtype") == "error":
                err_msg = data.get("result") or data.get("error") or "claude CLI error"
                return self.normalize_error(req.request_id, str(err_msg)[:300])
            content = data.get("result", "")
            usage = data.get("usage", {})
            return RouteResponse(
                request_id=req.request_id,
                selected_provider=self.name,
                output=RouteOutput(type=OutputType.TEXT, content=content),
                usage=RouteUsage(
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("input_tokens", 0)
                    + usage.get("output_tokens", 0),
                ),
                latency_ms=latency_ms,
                logs=logs,
            )
        except asyncio.TimeoutError:
            return self.normalize_error(
                req.request_id, f"claude CLI timed out after {timeout}s"
            )
        except Exception as e:
            logs.errors.append(f"native_claude subprocess error: {e}")
            return self.normalize_error(req.request_id, str(e)[:300])
