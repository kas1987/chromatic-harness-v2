"""Log/audit stage: JSONL route log, two-log audit span, and daily routing log."""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path(os.environ.get("ROUTER_LOG_DIR", Path.home() / ".claude" / ".agents" / "router"))
LOG_FILE = LOG_DIR / "log.jsonl"
MAX_LOG_LINES = int(os.environ.get("ROUTER_MAX_LOG_LINES", "2000"))

_REPO: Path | None = None


def _repo() -> Path:
    global _REPO
    if _REPO is None:
        _REPO = Path(__file__).resolve().parents[3]
    return _REPO


def log_entry(entry: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Lazy rotation: trim to 80% when over MAX_LOG_LINES.
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > MAX_LOG_LINES:
            keep = int(MAX_LOG_LINES * 0.8)
            with open(LOG_FILE, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-keep:])
    except Exception:
        pass


def audit_router_decision(entry: dict, billing_fn=None) -> None:
    """Write router.decision span + execution entry to two-log audit. Fail-open.

    billing_fn: callable(provider) -> dict with cost/axis keys. Defaults to
    importing pipeline.billing.billing_for_route to avoid circular imports at
    module load time.
    """
    try:
        repo = _repo()
        runtime_dir = repo / "02_RUNTIME"
        if str(runtime_dir) not in sys.path:
            sys.path.insert(0, str(runtime_dir))
        from audit.two_log import TwoLogAudit  # type: ignore[import]

        audit = TwoLogAudit(repo)
        audit.append_execution(
            {
                "event_type": "router.decision",
                "agent_role": "router",
                "task_id": "routing",
                "provider": entry.get("provider", ""),
                "model": entry.get("target_model", ""),
                "tier": entry.get("tier"),
                "blocked": entry.get("blocked", False),
                "c_level": entry.get("c_level", ""),
                "speed_mode": entry.get("speed_mode", ""),
                "reason": entry.get("reason", ""),
                "description": entry.get("description", "")[:120],
            }
        )
        audit.append_trace_span(
            {
                "name": "router.decision",
                "kind": "INTERNAL",
                "status": "OK",
                "duration_ms": 0,
                "attributes": {
                    "gen_ai.operation.name": "routing",
                    "gen_ai.request.model": entry.get("target_model", ""),
                    "router.provider": entry.get("provider", ""),
                    "router.tier": entry.get("tier"),
                    "router.blocked": entry.get("blocked", False),
                    "router.c_level": entry.get("c_level", ""),
                    "router.speed_mode": entry.get("speed_mode", ""),
                    "router.reason": entry.get("reason", ""),
                },
            }
        )

        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        routing_log = repo / "07_LOGS_AND_AUDIT" / "routing" / f"routes_{today}.jsonl"
        routing_log.parent.mkdir(parents=True, exist_ok=True)

        decision_id = entry.get("decision_id") or uuid.uuid4().hex[:16]
        if billing_fn is None:
            from router.pipeline.billing import billing_for_route as billing_fn  # type: ignore[assignment]
        _billing: dict[str, Any] = billing_fn(entry.get("provider", ""))

        with routing_log.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "decision_id": decision_id,
                        "request_id": uuid.uuid4().hex[:16],
                        "task_id": entry.get("description", "")[:80],
                        "task_type": entry.get("subagent_type", ""),
                        "caller": "gate.py",
                        "repo": str(repo),
                        "selected_provider": entry.get("provider", ""),
                        "selected_model": entry.get("target_model", ""),
                        "route_reason": entry.get("reason", ""),
                        "fallback_used": False,
                        "confidence_score": entry.get("c_confidence"),
                        "privacy_class": None,
                        "cost_estimate_usd": _billing["cost_estimate_usd"],
                        "billing_axis": _billing["billing_axis"],
                        "billing_tokens": _billing["billing_tokens"],
                        "budget_gate_estimate_usd": _billing["budget_gate_estimate_usd"],
                        "latency_ms": None,
                        "result_status": "blocked" if entry.get("blocked") else "allowed",
                        "warnings": [],
                        "errors": [],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception:  # noqa: BLE001
        pass
