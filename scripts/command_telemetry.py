#!/usr/bin/env python3
"""command_telemetry.py — command telemetry logging for Claude adapters (dnif / gh-106).

Records invocations of the governed adapter commands declared in
config/claude_command_registry.yaml to an append-only telemetry log under
07_LOGS_AND_AUDIT, so command usage (and mutation activity) is auditable and
queryable without re-deriving it from scattered per-command logs.

Append-only JSONL keeps it crash-safe and concurrent-friendly. Unknown command
names are recorded with known=false rather than rejected (telemetry must never
block a real invocation).

Dependency-light: PyYAML if available for registry validation, degrades safely.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "claude_command_registry.yaml"
TELEMETRY_DIR = ROOT / "07_LOGS_AND_AUDIT" / "command_telemetry"
TELEMETRY_LOG = TELEMETRY_DIR / "invocations.jsonl"
ARTIFACT_PATH = TELEMETRY_DIR / "latest.json"

STATUSES = {"started", "completed", "failed", "blocked"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def known_commands(registry_path: Path | None = None) -> set[str]:
    """Return the set of command names declared in the registry (empty on error)."""
    p = registry_path or REGISTRY_PATH
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return {c.get("name") for c in data.get("commands", []) if c.get("name")}
    except Exception:  # noqa: BLE001
        return set()


def log_invocation(
    command: str,
    *,
    actor: str = "unknown",
    status: str = "completed",
    mutated: bool = False,
    detail: str = "",
    registry_path: Path | None = None,
    path: Path | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Append one command-invocation telemetry record and return it."""
    p = path or TELEMETRY_LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    known = command in known_commands(registry_path)
    rec = {
        "invocation_id": f"inv-{uuid.uuid4().hex[:12]}",
        "timestamp": timestamp or _now_iso(),
        "command": command,
        "known": known,
        "actor": actor,
        "status": status if status in STATUSES else "completed",
        "mutated": bool(mutated),
        "detail": detail,
    }
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def load_invocations(path: Path | None = None) -> list[dict[str, Any]]:
    """Read all telemetry records; tolerant of partially-written lines."""
    p = path or TELEMETRY_LOG
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


def query(
    path: Path | None = None,
    *,
    command: str | None = None,
    actor: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    rows = load_invocations(path)
    if command is not None:
        rows = [r for r in rows if r.get("command") == command]
    if actor is not None:
        rows = [r for r in rows if r.get("actor") == actor]
    if status is not None:
        rows = [r for r in rows if r.get("status") == status]
    return rows


def summarize(path: Path | None = None) -> dict[str, Any]:
    """Fail-open rollup by command + mutation count, with artifact write."""
    try:
        rows = load_invocations(path)
        by_command: dict[str, int] = {}
        for r in rows:
            by_command[r.get("command", "?")] = by_command.get(r.get("command", "?"), 0) + 1
        result = {
            "status": "ok",
            "invocation_count": len(rows),
            "mutating_count": sum(1 for r in rows if r.get("mutated")),
            "unknown_count": sum(1 for r in rows if not r.get("known", False)),
            "by_command": by_command,
        }
    except Exception as exc:  # noqa: BLE001
        result = {"status": "error", "error": str(exc), "invocation_count": None}
    # Derive artifact path from log path when provided so test calls don't write to production.
    artifact = path.parent / "latest.json" if path else ARTIFACT_PATH
    try:
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Command telemetry logging (dnif)")
    parser.add_argument("--path", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    lg = sub.add_parser("log")
    lg.add_argument("--name", required=True, help="command name, e.g. /go")
    lg.add_argument("--actor", default="unknown")
    lg.add_argument("--status", default="completed", choices=sorted(STATUSES))
    lg.add_argument("--mutated", action="store_true")
    lg.add_argument("--detail", default="")

    q = sub.add_parser("query")
    q.add_argument("--name")
    q.add_argument("--actor")
    q.add_argument("--status")

    sub.add_parser("summarize")

    args = parser.parse_args()
    path = Path(args.path) if args.path else None

    if args.command == "log":
        rec = log_invocation(
            args.name, actor=args.actor, status=args.status, mutated=args.mutated, detail=args.detail, path=path
        )
        print(json.dumps(rec, indent=2))
        return 0
    if args.command == "query":
        rows = query(path, command=args.name, actor=args.actor, status=args.status)
        print(json.dumps(rows, indent=2))
        return 0
    if args.command == "summarize":
        print(json.dumps(summarize(path), indent=2))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
