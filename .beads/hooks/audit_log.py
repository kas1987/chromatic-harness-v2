#!/usr/bin/env python3
"""Append canonical AgentOps JSONL events.

This utility is intentionally small and dependency-free so hook scripts can call it
without introducing environment friction.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

DEFAULT_LOG_PATH = Path("logs/agentops-events.jsonl")
SCHEMA_VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_payload(raw_payload: str | None) -> Dict[str, Any]:
    if raw_payload:
        return json.loads(raw_payload)
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        if data:
            return json.loads(data)
    return {}


def build_event(args: argparse.Namespace, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event_id": args.event_id or str(uuid.uuid4()),
        "timestamp": args.timestamp or utc_now(),
        "schema_version": SCHEMA_VERSION,
        "event_type": args.event_type,
        "severity": args.severity,
        "source_repo": args.source_repo,
        "source_component": args.source_component,
        "agent_id": args.agent_id,
        "session_id": args.session_id,
        "task_id": args.task_id,
        "run_id": args.run_id,
        "parent_event_id": args.parent_event_id,
        "duration_ms": args.duration_ms,
        "payload": payload,
    }


def append_event(event: Dict[str, Any], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append an AgentOps JSONL event")
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--source-repo", default=os.getenv("AGENTOPS_SOURCE_REPO", "kas1987/claude-config"))
    parser.add_argument("--source-component", default=os.getenv("AGENTOPS_SOURCE_COMPONENT", "unknown"))
    parser.add_argument("--severity", default="info", choices=["debug", "info", "warning", "error", "critical"])
    parser.add_argument("--agent-id", default=os.getenv("AGENTOPS_AGENT_ID"))
    parser.add_argument("--session-id", default=os.getenv("AGENTOPS_SESSION_ID"))
    parser.add_argument("--task-id", default=os.getenv("AGENTOPS_TASK_ID"))
    parser.add_argument("--run-id", default=os.getenv("AGENTOPS_RUN_ID"))
    parser.add_argument("--parent-event-id")
    parser.add_argument("--duration-ms", type=float)
    parser.add_argument("--event-id")
    parser.add_argument("--timestamp")
    parser.add_argument("--payload", help="JSON object payload. If omitted, reads JSON from stdin when provided.")
    parser.add_argument("--log-path", default=os.getenv("AGENTOPS_LOG_PATH", str(DEFAULT_LOG_PATH)))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = read_payload(args.payload)
    event = build_event(args, payload)
    append_event(event, Path(args.log_path))
    print(json.dumps(event, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
