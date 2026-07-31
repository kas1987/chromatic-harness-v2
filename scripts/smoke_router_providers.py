#!/usr/bin/env python3
"""Reusable smoke check for router providers and auto-route behavior."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# Ensure imports work when launched from repo root.
REPO = Path(__file__).resolve().parents[1]
RUNTIME_DIR = REPO / "02_RUNTIME"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from router.contracts import (  # noqa: E402
    ConfidenceBand,
    RouteConfidence,
    RouteConstraints,
    RouteInput,
    RouteRequest,
    TaskType,
)
from router.router import ChromaticRouter  # noqa: E402


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


async def _provider_health(router: ChromaticRouter, providers: list[str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for provider in providers:
        adapter = router.adapters.get(provider)
        if adapter is None:
            results[provider] = {"ok": False, "error": "adapter_not_registered"}
            continue
        try:
            results[provider] = await adapter.health()
        except Exception as exc:  # defensive for smoke visibility
            results[provider] = {"ok": False, "error": str(exc)}
    return results


async def _provider_direct_smoke(
    router: ChromaticRouter,
    providers: list[str],
    prompt: str,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for provider in providers:
        adapter = router.adapters.get(provider)
        if adapter is None:
            out[provider] = {"ok": False, "error": "adapter_not_registered"}
            continue

        try:
            req = RouteRequest(
                request_id=f"smoke-direct-{provider}",
                task_id=f"smoke-direct-{provider}",
                task_type=TaskType.CODING,
                objective=f"Direct smoke for {provider}",
                input=RouteInput(messages=[{"role": "user", "content": prompt}]),
                constraints=RouteConstraints(max_tokens=1024),
                confidence=RouteConfidence(score=95.0, band=ConfidenceBand.VERY_HIGH, reason="smoke"),
                preferred_provider=provider,
            )
            resp = await adapter.complete(req)

            if hasattr(resp, "output") and hasattr(resp.output, "content"):
                preview = str(resp.output.content)[:160]
                output_type = getattr(resp.output, "type", "")
                output_type_value = getattr(output_type, "value", str(output_type))
                is_error = getattr(resp, "route_reason", "") == "adapter_error" or output_type_value == "error"
            elif isinstance(resp, dict):
                preview = str(resp.get("output", ""))[:160]
                is_error = str(resp.get("route_reason", "")) == "adapter_error"
            else:
                preview = str(resp)[:160]
                is_error = False

            out[provider] = {
                "ok": not is_error,
                "preview": preview,
                "raw": resp,
            }
        except Exception as exc:
            out[provider] = {"ok": False, "error": str(exc)}
    return out


async def _auto_route_smoke(router: ChromaticRouter, prompt: str, max_tokens: int) -> dict[str, Any]:
    req = RouteRequest(
        request_id="smoke-auto-route",
        task_id="smoke-auto-route",
        task_type=TaskType.CODING,
        objective="Provider auto-route smoke",
        input=RouteInput(messages=[{"role": "user", "content": prompt}]),
        constraints=RouteConstraints(
            privacy_class=RouteConstraints().privacy_class,
            max_tokens=max_tokens,
            max_context_resources=4,
            allow_cloud=True,
            allow_broker=True,
            allow_openhuman=False,
            allow_tools=False,
            allow_skills=True,
            allow_mcp=True,
        ),
        confidence=RouteConfidence(score=95.0, band=ConfidenceBand.VERY_HIGH, reason="smoke"),
        preferred_provider="auto",
    )
    resp = await router.route(req)
    return {
        "request": {
            "task_type": req.task_type.value,
            "privacy_class": req.constraints.privacy_class.value,
            "max_tokens": req.constraints.max_tokens,
            "max_context_resources": req.constraints.max_context_resources,
        },
        "response": {
            "selected_provider": resp.selected_provider,
            "selected_model": resp.selected_model,
            "route_reason": resp.route_reason,
            "output_type": resp.output.type.value,
            "output_preview": str(resp.output.content)[:200],
            "context_resources": resp.context_resources,
            "policy_checks": resp.logs.policy_checks,
            "warnings": resp.logs.warnings,
            "errors": resp.logs.errors,
        },
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    router = ChromaticRouter()

    summary: dict[str, Any] = {
        "env": {
            "OLLAMA_API_KEY_set": bool(os.getenv("OLLAMA_API_KEY")),
            "OLLAMA_PRO_KEY_set": bool(os.getenv("OLLAMA_PRO_KEY")),
        },
        "providers": providers,
    }

    summary["health"] = await _provider_health(router, providers)
    summary["direct"] = await _provider_direct_smoke(router, providers, args.prompt)

    if args.with_route:
        summary["route"] = await _auto_route_smoke(router, args.prompt, args.route_max_tokens)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test provider health/direct calls and optional auto-route")
    parser.add_argument(
        "--providers",
        default="agnes,ollama_cloud,native_claude,omniroute",
        help="Comma-separated provider names",
    )
    parser.add_argument(
        "--prompt",
        default="Return exactly: OK",
        help="Prompt used for direct and route smoke checks",
    )
    parser.add_argument(
        "--with-route",
        action="store_true",
        help="Include auto-route smoke run",
    )
    parser.add_argument(
        "--route-max-tokens",
        type=int,
        default=8192,
        help="max_tokens for route request balancing context gate and provider limits (default passes P1/C4 context gate)",
    )
    args = parser.parse_args()

    summary = asyncio.run(_run(args))
    print(json.dumps(_json_safe(summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
