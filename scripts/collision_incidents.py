#!/usr/bin/env python3
"""collision_incidents.py — autonomous collision incidents (P1-CC-009 / ju0o.8).

When a collision is detected (lease conflict, blocked write, deadlock, denied
claim), the detecting code records a structured incident to an append-only audit
trail. Incidents are queryable by type / agent / resource so post-mortems and
the harness dashboard can surface collision hot-spots without re-running scans.

No external deps; append-only JSONL keeps it crash-safe and concurrent-friendly.

Usage:
    python scripts/collision_incidents.py record --type blocked_write \\
        --agent AgentB --resource scripts/foo.py --detail "held by AgentA"
    python scripts/collision_incidents.py query --type blocked_write
    python scripts/collision_incidents.py summarize
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "07_LOGS_AND_AUDIT" / "collision"
INCIDENTS_PATH = ARTIFACT_DIR / "incidents.jsonl"

INCIDENT_TYPES = {
    "lease_conflict",
    "blocked_write",
    "deadlock",
    "denied_claim",
    "stale_recovery",
    "other",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def record_incident(
    incident_type: str,
    agent: str,
    resource: str = "",
    detail: str = "",
    *,
    path: Path | None = None,
    timestamp: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a collision incident to the audit trail and return the record."""
    p = path or INCIDENTS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "incident_id": f"inc-{uuid.uuid4().hex[:12]}",
        "timestamp": timestamp or _now_iso(),
        "type": incident_type if incident_type in INCIDENT_TYPES else "other",
        "agent": agent,
        "resource": resource,
        "detail": detail,
        "metadata": metadata or {},
    }
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def load_incidents(path: Path | None = None) -> list[dict[str, Any]]:
    """Read all incidents; tolerant of partially-written lines (fail-open)."""
    p = path or INCIDENTS_PATH
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def query_incidents(
    path: Path | None = None,
    *,
    incident_type: str | None = None,
    agent: str | None = None,
    resource: str | None = None,
) -> list[dict[str, Any]]:
    """Return incidents matching all supplied filters."""
    rows = load_incidents(path)
    if incident_type is not None:
        rows = [r for r in rows if r.get("type") == incident_type]
    if agent is not None:
        rows = [r for r in rows if r.get("agent") == agent]
    if resource is not None:
        rows = [r for r in rows if r.get("resource") == resource]
    return rows


def summarize(path: Path | None = None) -> dict[str, Any]:
    """Fail-open rollup of incidents by type for the harness dashboard."""
    try:
        rows = load_incidents(path)
        by_type: dict[str, int] = {}
        for r in rows:
            by_type[r.get("type", "other")] = by_type.get(r.get("type", "other"), 0) + 1
        return {"status": "ok", "incident_count": len(rows), "by_type": by_type}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "incident_count": None}


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous collision incidents (P1-CC-009)")
    parser.add_argument("--path", default=str(INCIDENTS_PATH))
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record")
    rec.add_argument("--type", required=True, dest="incident_type")
    rec.add_argument("--agent", required=True)
    rec.add_argument("--resource", default="")
    rec.add_argument("--detail", default="")

    q = sub.add_parser("query")
    q.add_argument("--type", dest="incident_type")
    q.add_argument("--agent")
    q.add_argument("--resource")

    sub.add_parser("summarize")

    args = parser.parse_args()
    path = Path(args.path)

    if args.command == "record":
        result = record_incident(args.incident_type, args.agent, args.resource, args.detail, path=path)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "query":
        result = query_incidents(
            path,
            incident_type=getattr(args, "incident_type", None),
            agent=args.agent,
            resource=args.resource,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "summarize":
        print(json.dumps(summarize(path), indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
