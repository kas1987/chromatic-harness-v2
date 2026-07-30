"""Agnes AI adapter using OpenAI-compatible API."""

from __future__ import annotations

import asyncio
import json
import os
import random
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


class AgnesAdapter(BaseAdapter):
    def __init__(self, cfg: dict[str, Any] | None = None):
        cfg = dict(cfg) if cfg else {}
        env_key = cfg.get("env_key", "AGNES_API_KEY")
        cfg["enabled"] = bool(os.environ.get(env_key))
        cfg.setdefault("env_key", "AGNES_API_KEY")
        cfg.setdefault("base_url", "https://apihub.agnes-ai.com/v1")
        cfg.setdefault("model", "agnes-2.5-flash")
        cfg.setdefault("temperature", 0.2)
        cfg.setdefault("timeout", 30)
        cfg.setdefault("max_retries", 3)
        cfg.setdefault("retry_base_delay_s", 0.5)
        cfg.setdefault("retry_max_delay_s", 4.0)
        cfg.setdefault("retry_max_attempt_interval_s", 8.0)
        cfg.setdefault("retry_jitter_ratio", 0.15)
        cfg.setdefault("retry_max_elapsed_s", 12.0)
        super().__init__("agnes", cfg)
        self._client: Any = None

    @staticmethod
    def _emit_retry_event(logs: RouteLogs, event: dict[str, Any]) -> None:
        logs.policy_checks.append(f"retry_event={json.dumps(event, sort_keys=True)}")

    @staticmethod
    def _http_status_from_error(exc: Exception) -> int | None:
        code = getattr(exc, "status_code", None)
        if isinstance(code, int):
            return code
        response = getattr(exc, "response", None)
        if response is None:
            return None
        status_code = getattr(response, "status_code", None)
        return status_code if isinstance(status_code, int) else None

    def _should_retry(self, exc: Exception) -> bool:
        status = self._http_status_from_error(exc)
        if status in {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524}:
            return True
        if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
            return True
        # OpenAI-compatible SDKs may raise typed connection/timeout exceptions
        # that are not always direct httpx subclasses.
        name = exc.__class__.__name__.lower()
        return "timeout" in name or "connection" in name or "ratelimit" in name

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=os.environ.get(self.cfg.get("env_key", "AGNES_API_KEY")),  # pragma: allowlist secret
                    base_url=self.cfg.get("base_url", "https://apihub.agnes-ai.com/v1"),
                )
            except ImportError:
                raise AdapterError("openai SDK not installed: pip install openai", provider="agnes")
        return self._client

    async def health(self) -> AdapterHealth:
        if not self.enabled:
            return AdapterHealth(reachable=False, latency_ms=0, error="AGNES_API_KEY not set")
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
                return self.normalize_error(req.request_id, "AGNES_API_KEY not configured")

            client = self._get_client()
            start = time.time()

            messages = req.input.messages if req.input.messages else [{"role": "user", "content": req.objective}]
            max_retries = int(self.cfg.get("max_retries", 3))
            retry_base = float(self.cfg.get("retry_base_delay_s", 0.5))
            retry_max = float(self.cfg.get("retry_max_delay_s", 4.0))
            retry_max_attempt_interval_s = max(0.0, float(self.cfg.get("retry_max_attempt_interval_s", 8.0)))
            retry_jitter_ratio = max(0.0, float(self.cfg.get("retry_jitter_ratio", 0.15)))
            retry_max_elapsed_s = max(0.0, float(self.cfg.get("retry_max_elapsed_s", 12.0)))
            response = None
            retry_started = time.monotonic()
            retries_used = 0

            for attempt in range(1, max_retries + 1):
                try:
                    response = await client.chat.completions.create(
                        model=self.cfg.get("model", "agnes-2.5-flash"),
                        messages=messages,
                        max_tokens=req.constraints.max_tokens or 2048,
                        temperature=float(self.cfg.get("temperature", 0.2)),
                        timeout=self.cfg.get("timeout", 30),
                    )
                    break
                except Exception as exc:
                    if attempt >= max_retries or not self._should_retry(exc):
                        self._emit_retry_event(
                            logs,
                            {
                                "type": "retry_stopped",
                                "attempt": attempt,
                                "max_retries": max_retries,
                                "retryable": self._should_retry(exc),
                                "reason": "attempt_limit" if attempt >= max_retries else "non_retryable",
                                "error_type": exc.__class__.__name__,
                            },
                        )
                        raise
                    base_delay_s = min(retry_max, retry_base * (2 ** (attempt - 1)))
                    jitter_s = random.uniform(0.0, base_delay_s * retry_jitter_ratio) if retry_jitter_ratio > 0 else 0.0
                    delay_s = min(retry_max, base_delay_s + jitter_s)
                    if retry_max_attempt_interval_s > 0:
                        delay_s = min(delay_s, retry_max_attempt_interval_s)

                    elapsed_s = time.monotonic() - retry_started
                    remaining_budget_s = retry_max_elapsed_s - elapsed_s
                    if remaining_budget_s <= 0:
                        self._emit_retry_event(
                            logs,
                            {
                                "type": "retry_budget_exhausted",
                                "attempt": attempt,
                                "elapsed_s": round(elapsed_s, 6),
                                "max_elapsed_s": retry_max_elapsed_s,
                                "error_type": exc.__class__.__name__,
                            },
                        )
                        raise
                    delay_s = min(delay_s, remaining_budget_s)
                    retries_used += 1

                    self._emit_retry_event(
                        logs,
                        {
                            "type": "retry_scheduled",
                            "attempt": attempt,
                            "max_retries": max_retries,
                            "base_delay_s": round(base_delay_s, 6),
                            "jitter_s": round(jitter_s, 6),
                            "delay_s": round(delay_s, 6),
                            "elapsed_s": round(elapsed_s, 6),
                            "remaining_budget_s": round(remaining_budget_s, 6),
                            "max_attempt_interval_s": retry_max_attempt_interval_s,
                            "error_type": exc.__class__.__name__,
                        },
                    )

                    logs.warnings.append(
                        f"Transient Agnes error (attempt {attempt}/{max_retries}): {exc}. Retrying in {delay_s:.2f}s."
                    )
                    await asyncio.sleep(delay_s)

            if response is None:
                raise AdapterError("Agnes response missing after retry loop", provider="agnes")

            self._emit_retry_event(
                logs,
                {
                    "type": "retry_summary",
                    "retries_used": retries_used,
                    "max_retries": max_retries,
                    "total_elapsed_s": round(time.monotonic() - retry_started, 6),
                },
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
            logs.errors.append(f"Agnes error: {str(e)}")
            return self.normalize_error(req.request_id, str(e))
