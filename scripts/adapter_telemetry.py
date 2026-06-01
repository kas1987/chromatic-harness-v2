#!/usr/bin/env python3
"""Telemetry logging for the 7 governed Claude adapter commands.

Every time a harness script is invoked via one of the adapter commands
(/go, /audit, /status, /ship, /recover, /queue, /explain) it should call
log_invocation() so the invocation is recorded for observability.

Log layout:
  07_LOGS_AND_AUDIT/adapter_telemetry/invocations.jsonl   — append-only event log
  07_LOGS_AND_AUDIT/adapter_telemetry/latest.json         — rolling summary

Record schema:
  {
    "ts":          "2026-06-01T18:00:00Z",   ISO-8601 UTC
    "run_id":      "tel_a1b2c3d4",           unique per invocation
    "command":     "/go",                    one of the 7 governed commands
    "mode":        "execute",                optional subcommand/mode
    "outcome":     "ok",                     ok | blocked | error | stop_condition
    "duration_ms": 450,                      optional elapsed time
    "detail":      "free text"               optional
  }

CLI:
  python scripts/adapter_telemetry.py log --command /go --outcome ok
  python scripts/adapter_telemetry.py tail [--n 10]
  python scripts/adapter_telemetry.py summarize

Importable API:
  from scripts.adapter_telemetry import log_invocation, summarize
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
TELEMETRY_DIR = REPO / "07_LOGS_AND_AUDIT" / "adapter_telemetry"
INVOCATION_LOG = TELEMETRY_DIR / "invocations.jsonl"
LATEST_JSON = TELEMETRY_DIR / "latest.json"

# The 7 governed adapter commands.
GOVERNED_COMMANDS = {"/go", "/audit", "/status", "/ship", "/recover", "/queue", "/explain"}
VALID_OUTCOMES = {"ok", "blocked", "error", "stop_condition"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _make_run_id() -> str:
    return "tel_" + uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def log_invocation(
    command: str,
    outcome: str,
    mode: str | None = None,
    duration_ms: int | None = None,
    detail: str | None = None,
    run_id: str | None = None,
    *,
    log_path: Path = INVOCATION_LOG,
) -> dict[str, Any]:
    """Append one invocation record to the telemetry log.

    Returns the record that was written so callers can inspect it in tests.
    Raises ValueError for unknown command or outcome.
    """
    if command not in GOVERNED_COMMANDS:
        raise ValueError(f"unknown command {command!r} — must be one of {sorted(GOVERNED_COMMANDS)}")
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r} — must be one of {sorted(VALID_OUTCOMES)}")

    record: dict[str, Any] = {
        "ts": _now_iso(),
        "run_id": run_id or _make_run_id(),
        "command": command,
        "outcome": outcome,
    }
    if mode is not None:
        record["mode"] = mode
    if duration_ms is not None:
        record["duration_ms"] = duration_ms
    if detail is not None:
        record["detail"] = detail

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")

    return record


def recent(n: int = 20, *, log_path: Path = INVOCATION_LOG) -> list[dict[str, Any]]:
    """Return the last n records from the invocation log (newest last)."""
    if not log_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records[-n:]


def build_summary(
    *,
    log_path: Path = INVOCATION_LOG,
    latest_path: Path = LATEST_JSON,
) -> dict[str, Any]:
    """Compute rolling summary and write latest.json; fail-open."""
    records = recent(n=0, log_path=log_path) if log_path.exists() else []
    # Use all records for summary (n=0 trick: read all then slice with no limit)
    all_records: list[dict[str, Any]] = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                all_records.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    by_command: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for r in all_records:
        cmd = r.get("command", "unknown")
        out = r.get("outcome", "unknown")
        by_command[cmd] = by_command.get(cmd, 0) + 1
        by_outcome[out] = by_outcome.get(out, 0) + 1

    summary = {
        "generated_at": _now_iso(),
        "total_invocations": len(all_records),
        "by_command": by_command,
        "by_outcome": by_outcome,
        "last_record": all_records[-1] if all_records else None,
    }
    try:
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        latest_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass
    return summary


def summarize(
    *,
    log_path: Path = INVOCATION_LOG,
    latest_path: Path = LATEST_JSON,
) -> str:
    """Return a one-line governance summary; fail-open if log missing."""
    try:
        summary = build_summary(log_path=log_path, latest_path=latest_path)
        total = summary["total_invocations"]
        errors = summary["by_outcome"].get("error", 0)
        blocked = summary["by_outcome"].get("blocked", 0)
        return f"adapter_telemetry: {total} invocations ({errors} errors, {blocked} blocked)"
    except Exception:  # noqa: BLE001
        return "adapter_telemetry: unavailable"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adapter command telemetry logging (dnif).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    log_p = sub.add_parser("log", help="Record one command invocation.")
    log_p.add_argument("--command", required=True, choices=sorted(GOVERNED_COMMANDS))
    log_p.add_argument("--outcome", required=True, choices=sorted(VALID_OUTCOMES))
    log_p.add_argument("--mode", default=None)
    log_p.add_argument("--duration-ms", type=int, default=None, dest="duration_ms")
    log_p.add_argument("--detail", default=None)
    log_p.add_argument("--run-id", default=None, dest="run_id")

    tail_p = sub.add_parser("tail", help="Show recent invocations.")
    tail_p.add_argument("--n", type=int, default=10)

    sub.add_parser("summarize", help="Compute rolling summary and write latest.json.")

    args = parser.parse_args(argv)

    if args.cmd == "log":
        record = log_invocation(
            command=args.command,
            outcome=args.outcome,
            mode=args.mode,
            duration_ms=args.duration_ms,
            detail=args.detail,
            run_id=args.run_id,
        )
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0

    if args.cmd == "tail":
        records = recent(n=args.n)
        print(json.dumps(records, indent=2, sort_keys=True))
        return 0

    if args.cmd == "summarize":
        summary = build_summary()
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
