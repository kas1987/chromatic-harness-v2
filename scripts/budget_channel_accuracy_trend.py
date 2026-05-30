#!/usr/bin/env python3
"""Compute channel forecast-accuracy trend from historical scorecards."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
BUDGET_DIR = REPO / "07_LOGS_AND_AUDIT" / "budget"
HISTORY = BUDGET_DIR / "forecast_accuracy_history.jsonl"
OUT_JSON = BUDGET_DIR / "forecast_channel_trend_latest.json"
OUT_MD = BUDGET_DIR / "forecast_channel_trend_latest.md"
CHANNEL_KEYS = ("vscode", "cursor", "claude_code", "codex", "cli", "other")


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    rows.sort(key=lambda r: _parse_ts(r.get("generated_at")) or datetime.min.replace(tzinfo=timezone.utc))
    return rows


def _avg(values: list[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def build_trend(now: datetime | None = None) -> dict[str, Any]:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows = _read_jsonl(HISTORY)

    channels: dict[str, Any] = {}
    worst_delta = 0.0
    for key in CHANNEL_KEYS:
        samples: list[float] = []
        for row in rows:
            ch = (row.get("channels") or {}).get(key) if isinstance(row.get("channels"), dict) else {}
            week = (ch.get("week") or {}) if isinstance(ch, dict) else {}
            try:
                mape = float(week.get("mape_pct", 0.0) or 0.0)
                count = int(week.get("samples", 0) or 0)
            except (TypeError, ValueError):
                continue
            if count > 0:
                samples.append(mape)

        latest = samples[-1] if samples else 0.0
        prev = _avg(samples[-5:-1]) if len(samples) >= 2 else 0.0
        delta = round(latest - prev, 2) if samples else 0.0
        worst_delta = max(worst_delta, delta)
        channels[key] = {
            "points": len(samples),
            "week_mape_latest": round(latest, 2),
            "week_mape_prev_avg": round(prev, 2),
            "week_mape_delta": delta,
            "trend": "worse" if delta > 2 else ("better" if delta < -2 else "flat"),
        }

    if worst_delta > 12:
        status = "red"
    elif worst_delta > 5:
        status = "yellow"
    else:
        status = "green"

    return {
        "generated_at": now_utc.isoformat(),
        "status": status,
        "coverage": {"history_rows": len(rows)},
        "channels": channels,
    }


def _to_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Channel Forecast Accuracy Trend",
        "",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- status: {payload.get('status', 'unknown')}",
        "",
        "| Channel | Points | Latest Week MAPE | Prev Avg | Delta | Trend |",
        "|---|---:|---:|---:|---:|---|",
    ]
    channels = payload.get("channels") if isinstance(payload.get("channels"), dict) else {}
    for key in CHANNEL_KEYS:
        c = channels.get(key) if isinstance(channels.get(key), dict) else {}
        lines.append(
            f"| {key} | {c.get('points', 0)} | {c.get('week_mape_latest', 0)} | {c.get('week_mape_prev_avg', 0)} | {c.get('week_mape_delta', 0)} | {c.get('trend', 'flat')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build per-channel forecast accuracy trend report")
    parser.add_argument("--write", action="store_true", help="Write trend artifacts")
    args = parser.parse_args()

    payload = build_trend()
    if args.write:
        BUDGET_DIR.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        OUT_MD.write_text(_to_md(payload), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())