#!/usr/bin/env python3
"""Analyze auto-turn observations and recommend threshold calibrations.

Usage:
  python scripts/analyze_auto_turn_observations.py --write
  python scripts/analyze_auto_turn_observations.py --window-days 14 --write
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO / ".agents" / "handoffs" / "auto_turn_observations.jsonl"
OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "auto_turn_thresholds"


def _parse_ts(raw: str) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _p70(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * 0.70))
    return int(ordered[max(0, min(idx, len(ordered) - 1))])


def _recommend(filtered: list[dict[str, Any]]) -> dict[str, Any]:
    triggered = [r for r in filtered if bool(r.get("triggered_closeout"))]
    loc_values = [int(r.get("loc_insertions", 0)) + int(r.get("loc_deletions", 0)) for r in triggered]
    event_values = [int(r.get("policy_event_count", 0)) for r in triggered]
    open_task_values = [int(r.get("beads_ready_count", 0)) for r in triggered]
    changed_values = [int(r.get("git_changed_files", 0)) for r in triggered]
    turn_threshold_values = [int(r.get("auto_turn_threshold", 0)) for r in filtered if int(r.get("auto_turn_threshold", 0)) > 0]

    recommended_turn_threshold = 5
    if turn_threshold_values:
        recommended_turn_threshold = max(3, int(round(statistics.median(turn_threshold_values))))

    rec = {
        "required_signal_hits": 2,
        "turn_threshold": recommended_turn_threshold,
        "signals": {
            "loc_delta_total": max(200, _p70(loc_values)),
            "policy_event_count": max(100, _p70(event_values)),
            "open_tasks": max(2, _p70(open_task_values)),
            "changed_files": max(6, _p70(changed_values)),
        },
        "sample_sizes": {
            "rows_total": len(filtered),
            "rows_triggered": len(triggered),
        },
    }
    return rec


def _markdown(report: dict[str, Any]) -> str:
    generated = report.get("generated_at_utc", "")
    window_days = int(report.get("window_days") or 0)
    input_path = report.get("input_path", "")
    rec = report.get("recommendations") or {}
    signals = rec.get("signals") or {}
    sample = rec.get("sample_sizes") or {}
    lines = [
        "---",
        "name: auto-turn-threshold-calibration",
        "confidence: 0.82",
        "status: candidate",
        "category: governance",
        "tags: auto-turn, rpi, checkpoint, policy, telemetry",
        "---",
        "",
        "# Auto-Turn Threshold Calibration",
        "",
        f"- generated_at_utc: {generated}",
        f"- window_days: {window_days}",
        f"- input_path: {input_path}",
        f"- rows_total: {int(sample.get('rows_total') or 0)}",
        f"- rows_triggered: {int(sample.get('rows_triggered') or 0)}",
        "",
        "## Recommended Trigger Policy",
        f"- required_signal_hits: {int(rec.get('required_signal_hits') or 2)}",
        f"- turn_threshold: {int(rec.get('turn_threshold') or 5)}",
        f"- loc_delta_total.min: {int(signals.get('loc_delta_total') or 400)}",
        f"- policy_event_count.min: {int(signals.get('policy_event_count') or 200)}",
        f"- open_tasks.min: {int(signals.get('open_tasks') or 4)}",
        f"- changed_files.min: {int(signals.get('changed_files') or 12)}",
        "",
        "## Convergence Notes",
        "- This report is generated from observed closeout behavior to calibrate checkpoint timing.",
        "- Promote this file into the wiki to keep RPI threshold governance synchronized across rigs.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze auto-turn observation logs")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to auto_turn_observations.jsonl")
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--write", action="store_true", help="Write latest.json and latest.md outputs")
    args = parser.parse_args()

    in_path = Path(args.input)
    rows = _read_rows(in_path)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=max(1, int(args.window_days)))

    filtered: list[dict[str, Any]] = []
    for row in rows:
        ts = _parse_ts(str(row.get("timestamp_utc") or ""))
        if ts is None:
            continue
        if ts < start:
            continue
        filtered.append(row)

    recommendations = _recommend(filtered)
    report = {
        "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_days": int(args.window_days),
        "input_path": str(in_path),
        "recommendations": recommendations,
    }

    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (OUT_DIR / "latest.md").write_text(_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
