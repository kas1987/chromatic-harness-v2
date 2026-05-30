#!/usr/bin/env python3
"""Evaluate budget forecast accuracy against realized usage.

Reads forecast history and daily spend ledger, computes horizon error metrics,
and writes latest accuracy artifacts for tuning loops.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
BUDGET_DIR = REPO / "07_LOGS_AND_AUDIT" / "budget"
HISTORY = BUDGET_DIR / "forecast_history.jsonl"
DAILY = BUDGET_DIR / "daily.jsonl"
OUT_JSON = BUDGET_DIR / "forecast_accuracy_latest.json"
OUT_MD = BUDGET_DIR / "forecast_accuracy_latest.md"
HISTORY_JSONL = BUDGET_DIR / "forecast_accuracy_history.jsonl"
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
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _normalize_channel(row: dict[str, Any]) -> str:
    raw = str(
        row.get("source")
        or row.get("runtime")
        or row.get("editor")
        or row.get("channel")
        or ""
    ).strip().lower()
    if "vscode" in raw or "vs code" in raw:
        return "vscode"
    if "cursor" in raw:
        return "cursor"
    if "claude" in raw:
        return "claude_code"
    if "codex" in raw:
        return "codex"
    if raw in {"cli", "terminal", "shell"} or "cli" in raw:
        return "cli"
    return "other"


def _build_daily_totals(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        ts = _parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        day = ts.strftime("%Y-%m-%d")
        try:
            totals[day] = totals.get(day, 0.0) + float(row.get("amount_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
    return totals


def _build_daily_totals_by_channel(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {k: {} for k in CHANNEL_KEYS}
    for row in rows:
        ts = _parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        day = ts.strftime("%Y-%m-%d")
        ch = _normalize_channel(row)
        try:
            amount = float(row.get("amount_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        bucket = out.setdefault(ch, {})
        bucket[day] = bucket.get(day, 0.0) + amount
    return out


def _sum_range(totals: dict[str, float], start: datetime, end_exclusive: datetime) -> float:
    s = 0.0
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_exclusive.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        s += totals.get(day.strftime("%Y-%m-%d"), 0.0)
        day += timedelta(days=1)
    return s


def _err(pred: float, actual: float) -> dict[str, float]:
    abs_err = abs(pred - actual)
    ape = (abs_err / abs(actual) * 100.0) if abs(actual) > 1e-9 else (0.0 if abs(pred) <= 1e-9 else 100.0)
    return {"pred": round(pred, 4), "actual": round(actual, 4), "abs_error": round(abs_err, 4), "ape_pct": round(ape, 2)}


def build_accuracy(now: datetime | None = None) -> dict[str, Any]:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    hist = _read_jsonl(HISTORY)
    spend_rows = _read_jsonl(DAILY)
    daily_totals = _build_daily_totals(spend_rows)
    daily_by_channel = _build_daily_totals_by_channel(spend_rows)

    records: list[dict[str, Any]] = []
    channel_records: dict[str, list[dict[str, Any]]] = {k: [] for k in CHANNEL_KEYS}
    for row in hist:
        ts = _parse_ts(row.get("generated_at"))
        if ts is None:
            continue
        forecast = row.get("forecast") if isinstance(row.get("forecast"), dict) else {}
        if not forecast:
            continue

        day_end = ts.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        week_start = ts.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
        week_end = week_start + timedelta(days=7)
        month_start = ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1)

        if day_end > now_utc:
            continue

        pred_day = float(forecast.get("end_of_day_usd", 0.0) or 0.0)
        pred_week = float(forecast.get("end_of_week_usd", 0.0) or 0.0)
        pred_month = float(forecast.get("end_of_month_usd", 0.0) or 0.0)

        actual_day = _sum_range(daily_totals, ts, day_end)
        actual_week = _sum_range(daily_totals, week_start, week_end)
        actual_month = _sum_range(daily_totals, month_start, month_end)

        rec = {
            "generated_at": ts.isoformat(),
            "day": _err(pred_day, actual_day),
            "week": _err(pred_week, actual_week),
            "month": _err(pred_month, actual_month),
        }
        records.append(rec)

        channels = row.get("channels") if isinstance(row.get("channels"), dict) else {}
        for key in CHANNEL_KEYS:
            c = channels.get(key) if isinstance(channels.get(key), dict) else None
            if not c:
                continue
            try:
                c_pred_day = float(c.get("end_of_day_usd", 0.0) or 0.0)
                c_pred_week = float(c.get("end_of_week_usd", 0.0) or 0.0)
                c_pred_month = float(c.get("end_of_month_usd", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            totals = daily_by_channel.get(key, {})
            c_actual_day = _sum_range(totals, ts, day_end)
            c_actual_week = _sum_range(totals, week_start, week_end)
            c_actual_month = _sum_range(totals, month_start, month_end)
            channel_records[key].append(
                {
                    "generated_at": ts.isoformat(),
                    "day": _err(c_pred_day, c_actual_day),
                    "week": _err(c_pred_week, c_actual_week),
                    "month": _err(c_pred_month, c_actual_month),
                }
            )

    def _agg(h: str) -> dict[str, Any]:
        if not records:
            return {"samples": 0, "mae_usd": 0.0, "mape_pct": 0.0}
        mae = sum(r[h]["abs_error"] for r in records) / len(records)
        mape = sum(r[h]["ape_pct"] for r in records) / len(records)
        return {"samples": len(records), "mae_usd": round(mae, 4), "mape_pct": round(mape, 2)}

    day = _agg("day")
    week = _agg("week")
    month = _agg("month")

    def _agg_rows(rows: list[dict[str, Any]], horizon: str) -> dict[str, Any]:
        if not rows:
            return {"samples": 0, "mae_usd": 0.0, "mape_pct": 0.0}
        mae = sum(r[horizon]["abs_error"] for r in rows) / len(rows)
        mape = sum(r[horizon]["ape_pct"] for r in rows) / len(rows)
        return {"samples": len(rows), "mae_usd": round(mae, 4), "mape_pct": round(mape, 2)}

    channel_metrics: dict[str, Any] = {}
    for key in CHANNEL_KEYS:
        rows_for_key = channel_records.get(key) or []
        channel_metrics[key] = {
            "day": _agg_rows(rows_for_key, "day"),
            "week": _agg_rows(rows_for_key, "week"),
            "month": _agg_rows(rows_for_key, "month"),
        }

    tuning = []
    if week["samples"] >= 5 and week["mape_pct"] > 30:
        tuning.append("weekly forecast mape high; increase smoothing window")
    if day["samples"] >= 5 and day["mape_pct"] > 40:
        tuning.append("daily forecast noisy; reduce intraday projection weight")

    status = "green"
    if week["mape_pct"] > 35 or day["mape_pct"] > 45:
        status = "yellow"
    if week["mape_pct"] > 55:
        status = "red"

    return {
        "generated_at": now_utc.isoformat(),
        "status": status,
        "coverage": {
            "forecast_rows": len(hist),
            "daily_ledger_rows": len(spend_rows),
            "scored_rows": len(records),
        },
        "metrics": {"day": day, "week": week, "month": month},
        "channels": channel_metrics,
        "recommendations": tuning,
        "latest": records[-5:],
    }


def _to_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Budget Forecast Accuracy",
        "",
        f"- generated_at: {payload.get('generated_at','')}",
        f"- status: {payload.get('status','unknown')}",
        "",
        "## Metrics",
        "",
        "| Horizon | Samples | MAE USD | MAPE % |",
        "|---|---:|---:|---:|",
    ]
    metrics = payload.get("metrics") or {}
    for h in ("day", "week", "month"):
        m = metrics.get(h) or {}
        lines.append(f"| {h} | {m.get('samples',0)} | {m.get('mae_usd',0)} | {m.get('mape_pct',0)} |")
    recs = payload.get("recommendations") or []
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    if recs:
        for r in recs:
            lines.append(f"- {r}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute budget forecast accuracy")
    parser.add_argument("--write", action="store_true", help="Write latest accuracy artifacts")
    args = parser.parse_args()

    payload = build_accuracy()
    if args.write:
        BUDGET_DIR.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        OUT_MD.write_text(_to_md(payload), encoding="utf-8")
        history_row = {
            "generated_at": payload.get("generated_at"),
            "status": payload.get("status"),
            "metrics": payload.get("metrics") or {},
            "channels": payload.get("channels") or {},
            "coverage": payload.get("coverage") or {},
        }
        with HISTORY_JSONL.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(history_row) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())