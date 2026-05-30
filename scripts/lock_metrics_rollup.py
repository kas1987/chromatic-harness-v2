#!/usr/bin/env python3
"""Roll up lock telemetry from workflow run log for contention monitoring."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RUN_LOG = REPO / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"
OUT_DIR = REPO / ".agents" / "audits" / "locks"

TEST_SESSION_IDS = {"holder", "contender", "pytest", "unit-test"}


def _is_test_event(entry: dict[str, Any]) -> bool:
    owner = str(entry.get("lock_owner", "")).strip().lower()
    lock_name = str(entry.get("lock_name", "")).strip().lower()
    if not owner and lock_name == "unit-lock":
        return True
    if owner in TEST_SESSION_IDS:
        return True
    if owner.startswith("test-") or owner.startswith("pytest"):
        return True
    return False


def _parse_iso(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * p))
    idx = max(0, min(idx, len(ordered) - 1))
    return ordered[idx]


def _collect_events(log_path: Path, since: datetime, *, include_test_events: bool) -> tuple[list[dict[str, Any]], int]:
    if not log_path.is_file():
        return [], 0
    rows: list[dict[str, Any]] = []
    excluded = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("event_type") not in ("lock.acquire", "lock.timeout"):
            continue
        ts = _parse_iso(str(entry.get("timestamp", "")))
        if ts is None or ts < since:
            continue
        if not include_test_events and _is_test_event(entry):
            excluded += 1
            continue
        rows.append(entry)
    return rows, excluded


def build_rollup(*, log_path: Path, lookback_days: int, include_test_events: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    days = max(1, lookback_days)
    start_date = (now - timedelta(days=days - 1)).date()
    since = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    events, excluded_count = _collect_events(log_path, since, include_test_events=include_test_events)

    waits = [int(e.get("lock_wait_ms", 0)) for e in events if e.get("event_type") == "lock.acquire"]
    timeouts = [e for e in events if e.get("event_type") == "lock.timeout"]

    by_lock: dict[str, dict[str, int]] = {}
    by_day: dict[str, dict[str, int]] = {}

    for i in range(days):
        day = (start_date + timedelta(days=i)).isoformat()
        by_day[day] = {"acquire": 0, "timeout": 0}

    for event in events:
        lock_name = str(event.get("lock_name", "unknown"))
        bucket = by_lock.setdefault(lock_name, {"acquire": 0, "timeout": 0})
        ts = _parse_iso(str(event.get("timestamp", "")))
        day_key = ts.date().isoformat() if ts else "unknown"
        day_bucket = by_day.setdefault(day_key, {"acquire": 0, "timeout": 0})
        if event.get("event_type") == "lock.acquire":
            bucket["acquire"] += 1
            day_bucket["acquire"] += 1
        elif event.get("event_type") == "lock.timeout":
            bucket["timeout"] += 1
            day_bucket["timeout"] += 1

    acquire_count = len(waits)
    timeout_count = len(timeouts)
    total = acquire_count + timeout_count
    timeout_rate = round((timeout_count / total), 4) if total else 0.0

    return {
        "ok": True,
        "generated_at": now.isoformat(),
        "lookback_days": lookback_days,
        "window_start": since.isoformat(),
        "window_end": now.isoformat(),
        "event_counts": {
            "acquire": acquire_count,
            "timeout": timeout_count,
            "total": total,
            "excluded_test_events": excluded_count,
        },
        "wait_ms": {
            "p50": _percentile(waits, 0.5),
            "p95": _percentile(waits, 0.95),
            "max": max(waits) if waits else 0,
            "avg": int(sum(waits) / len(waits)) if waits else 0,
        },
        "timeout_rate": timeout_rate,
        "include_test_events": include_test_events,
        "by_lock": by_lock,
        "trend_daily": [
            {
                "date": day,
                "acquire": counts["acquire"],
                "timeout": counts["timeout"],
                "total": counts["acquire"] + counts["timeout"],
                "timeout_rate": (
                    round(counts["timeout"] / (counts["acquire"] + counts["timeout"]), 4)
                    if (counts["acquire"] + counts["timeout"])
                    else 0.0
                ),
            }
            for day, counts in sorted(by_day.items())
        ],
    }


def _write_reports(result: dict[str, Any]) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "latest_lock_metrics.json"
    md_path = OUT_DIR / "latest_lock_metrics.md"

    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Lock Metrics Rollup",
        "",
        f"Generated: `{result.get('generated_at', '')}`",
        f"Window: `{result.get('window_start', '')}` to `{result.get('window_end', '')}`",
        "",
        "## Counts",
        "",
        f"- Acquire: {result['event_counts']['acquire']}",
        f"- Timeout: {result['event_counts']['timeout']}",
        f"- Timeout rate: {result['timeout_rate']}",
        "",
        "## Wait (ms)",
        "",
        f"- p50: {result['wait_ms']['p50']}",
        f"- p95: {result['wait_ms']['p95']}",
        f"- avg: {result['wait_ms']['avg']}",
        f"- max: {result['wait_ms']['max']}",
        "",
        "## Trend (Daily)",
        "",
        "| Date | Acquire | Timeout | Total | Timeout Rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in result.get("trend_daily", []):
        lines.append(
            f"| {row.get('date','')} | {row.get('acquire',0)} | {row.get('timeout',0)} | "
            f"{row.get('total',0)} | {row.get('timeout_rate',0.0)} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "json": str(json_path.relative_to(REPO)),
        "markdown": str(md_path.relative_to(REPO)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Roll up lock telemetry from workflow run log")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--write", action="store_true", help="Write reports under .agents/audits/locks")
    parser.add_argument(
        "--include-test-events",
        action="store_true",
        help="Include synthetic lock telemetry emitted by tests",
    )
    args = parser.parse_args()

    result = build_rollup(
        log_path=RUN_LOG,
        lookback_days=args.lookback_days,
        include_test_events=args.include_test_events,
    )
    if args.write:
        result["report_paths"] = _write_reports(result)

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
