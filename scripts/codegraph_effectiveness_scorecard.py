#!/usr/bin/env python3
"""Track and summarize CodeGraph effectiveness with simple A/B logging.

Usage examples:
  python scripts/codegraph_effectiveness_scorecard.py log \
    --task-id arch-001 --mode with --duration-sec 95 --discovery-calls 4 --tokens 420000 --cost-usd 0.42

  python scripts/codegraph_effectiveness_scorecard.py log \
    --task-id arch-001 --mode without --duration-sec 140 --discovery-calls 13 --tokens 980000 --cost-usd 0.79

  python scripts/codegraph_effectiveness_scorecard.py summary --window-days 14 --write
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "codegraph_effectiveness"
CSV_PATH = OUT_DIR / "runs.csv"
SUMMARY_JSON = OUT_DIR / "summary_latest.json"
SUMMARY_MD = OUT_DIR / "summary_latest.md"

CSV_FIELDS = [
    "timestamp_utc",
    "task_id",
    "task_type",
    "mode",
    "duration_sec",
    "discovery_calls",
    "tokens",
    "cost_usd",
    "impact_precision",
    "impact_recall",
    "notes",
]


@dataclass
class RunRow:
    timestamp_utc: str
    task_id: str
    task_type: str
    mode: str
    duration_sec: float
    discovery_calls: int
    tokens: int
    cost_usd: float
    impact_precision: float | None
    impact_recall: float | None
    notes: str


def _ensure_csv() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if CSV_PATH.is_file():
        return
    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()


def _safe_float(raw: Any, default: float = 0.0) -> float:
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _safe_int(raw: Any, default: int = 0) -> int:
    if raw is None:
        return default
    s = str(raw).strip()
    if not s:
        return default
    try:
        return int(float(s))
    except ValueError:
        return default


def _parse_dt(raw: str) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def _read_rows(window_days: int) -> list[RunRow]:
    if not CSV_PATH.is_file():
        return []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, int(window_days)))
    rows: list[RunRow] = []

    with CSV_PATH.open("r", newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            ts = _parse_dt(str(raw.get("timestamp_utc") or ""))
            if ts is None or ts < cutoff:
                continue

            precision_raw = str(raw.get("impact_precision") or "").strip()
            recall_raw = str(raw.get("impact_recall") or "").strip()

            rows.append(
                RunRow(
                    timestamp_utc=str(raw.get("timestamp_utc") or ""),
                    task_id=str(raw.get("task_id") or "").strip(),
                    task_type=str(raw.get("task_type") or "").strip(),
                    mode=str(raw.get("mode") or "").strip().lower(),
                    duration_sec=_safe_float(raw.get("duration_sec"), 0.0),
                    discovery_calls=_safe_int(raw.get("discovery_calls"), 0),
                    tokens=_safe_int(raw.get("tokens"), 0),
                    cost_usd=_safe_float(raw.get("cost_usd"), 0.0),
                    impact_precision=None if not precision_raw else _safe_float(precision_raw, 0.0),
                    impact_recall=None if not recall_raw else _safe_float(recall_raw, 0.0),
                    notes=str(raw.get("notes") or "").strip(),
                )
            )

    return rows


def _median(values: list[float | int]) -> float:
    if not values:
        return 0.0
    return float(median(values))


def _pct_change(with_val: float, without_val: float) -> float:
    if without_val <= 0:
        return 0.0
    return ((without_val - with_val) / without_val) * 100.0


def _build_summary(rows: list[RunRow], window_days: int) -> dict[str, Any]:
    with_rows = [r for r in rows if r.mode == "with"]
    without_rows = [r for r in rows if r.mode == "without"]

    paired_ids = sorted({r.task_id for r in with_rows if r.task_id} & {r.task_id for r in without_rows if r.task_id})

    med_with_duration = _median([r.duration_sec for r in with_rows])
    med_without_duration = _median([r.duration_sec for r in without_rows])
    med_with_discovery = _median([r.discovery_calls for r in with_rows])
    med_without_discovery = _median([r.discovery_calls for r in without_rows])
    med_with_tokens = _median([r.tokens for r in with_rows])
    med_without_tokens = _median([r.tokens for r in without_rows])
    med_with_cost = _median([r.cost_usd for r in with_rows])
    med_without_cost = _median([r.cost_usd for r in without_rows])

    with_precision = [r.impact_precision for r in with_rows if r.impact_precision is not None]
    without_precision = [r.impact_precision for r in without_rows if r.impact_precision is not None]
    with_recall = [r.impact_recall for r in with_rows if r.impact_recall is not None]
    without_recall = [r.impact_recall for r in without_rows if r.impact_recall is not None]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_days": int(window_days),
        "rows_total": len(rows),
        "rows_with": len(with_rows),
        "rows_without": len(without_rows),
        "paired_task_ids": paired_ids,
        "paired_count": len(paired_ids),
        "medians": {
            "with": {
                "duration_sec": round(med_with_duration, 2),
                "discovery_calls": round(med_with_discovery, 2),
                "tokens": round(med_with_tokens, 2),
                "cost_usd": round(med_with_cost, 4),
                "impact_precision": round(_median(with_precision), 4) if with_precision else None,
                "impact_recall": round(_median(with_recall), 4) if with_recall else None,
            },
            "without": {
                "duration_sec": round(med_without_duration, 2),
                "discovery_calls": round(med_without_discovery, 2),
                "tokens": round(med_without_tokens, 2),
                "cost_usd": round(med_without_cost, 4),
                "impact_precision": round(_median(without_precision), 4) if without_precision else None,
                "impact_recall": round(_median(without_recall), 4) if without_recall else None,
            },
        },
        "improvements_pct": {
            "duration_sec": round(_pct_change(med_with_duration, med_without_duration), 2),
            "discovery_calls": round(_pct_change(med_with_discovery, med_without_discovery), 2),
            "tokens": round(_pct_change(med_with_tokens, med_without_tokens), 2),
            "cost_usd": round(_pct_change(med_with_cost, med_without_cost), 2),
        },
    }

    return summary


def _markdown(summary: dict[str, Any]) -> str:
    med = summary.get("medians") or {}
    mw = med.get("with") or {}
    mwo = med.get("without") or {}
    imp = summary.get("improvements_pct") or {}

    lines = [
        "# CodeGraph Effectiveness Scorecard",
        "",
        f"- generated_at_utc: {summary.get('generated_at_utc', '')}",
        f"- window_days: {int(summary.get('window_days') or 0)}",
        f"- rows_total: {int(summary.get('rows_total') or 0)}",
        f"- rows_with: {int(summary.get('rows_with') or 0)}",
        f"- rows_without: {int(summary.get('rows_without') or 0)}",
        f"- paired_count: {int(summary.get('paired_count') or 0)}",
        "",
        "## Median Comparison",
        "",
        "| Metric | With CodeGraph | Without CodeGraph | Improvement % |",
        "|---|---:|---:|---:|",
        f"| duration_sec | {mw.get('duration_sec')} | {mwo.get('duration_sec')} | {imp.get('duration_sec')} |",
        f"| discovery_calls | {mw.get('discovery_calls')} | {mwo.get('discovery_calls')} | {imp.get('discovery_calls')} |",
        f"| tokens | {mw.get('tokens')} | {mwo.get('tokens')} | {imp.get('tokens')} |",
        f"| cost_usd | {mw.get('cost_usd')} | {mwo.get('cost_usd')} | {imp.get('cost_usd')} |",
        "",
    ]

    if mw.get("impact_precision") is not None or mwo.get("impact_precision") is not None:
        lines.append("## Impact Quality")
        lines.append("")
        lines.append(f"- median_precision_with: {mw.get('impact_precision')}")
        lines.append(f"- median_precision_without: {mwo.get('impact_precision')}")
        lines.append(f"- median_recall_with: {mw.get('impact_recall')}")
        lines.append(f"- median_recall_without: {mwo.get('impact_recall')}")
        lines.append("")

    lines.append("## Paired Task IDs")
    lines.append("")
    paired = summary.get("paired_task_ids") or []
    if paired:
        for task_id in paired[:50]:
            lines.append(f"- {task_id}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def cmd_log(args: argparse.Namespace) -> int:
    _ensure_csv()

    row = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task_id": str(args.task_id).strip(),
        "task_type": str(args.task_type or "").strip(),
        "mode": str(args.mode).strip().lower(),
        "duration_sec": float(args.duration_sec),
        "discovery_calls": int(args.discovery_calls),
        "tokens": int(args.tokens),
        "cost_usd": float(args.cost_usd),
        "impact_precision": "" if args.impact_precision is None else float(args.impact_precision),
        "impact_recall": "" if args.impact_recall is None else float(args.impact_recall),
        "notes": str(args.notes or "").strip(),
    }

    with CSV_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writerow(row)

    print(json.dumps({"ok": True, "csv_path": str(CSV_PATH), "row": row}, indent=2))
    return 0


def cmd_summary(args: argparse.Namespace) -> int:
    _ensure_csv()
    rows = _read_rows(window_days=args.window_days)
    summary = _build_summary(rows=rows, window_days=args.window_days)

    if args.write:
        SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        SUMMARY_MD.write_text(_markdown(summary), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


def cmd_kpi(args: argparse.Namespace) -> int:
    _ensure_csv()
    rows = _read_rows(window_days=args.window_days)
    summary = _build_summary(rows=rows, window_days=args.window_days)

    imp = summary.get("improvements_pct") or {}
    paired_count = int(summary.get("paired_count") or 0)
    rows_total = int(summary.get("rows_total") or 0)
    window_days = int(summary.get("window_days") or 0)

    line = (
        f"CodeGraph KPI ({window_days}d): "
        f"duration={imp.get('duration_sec', 0.0)}% "
        f"discovery={imp.get('discovery_calls', 0.0)}% "
        f"tokens={imp.get('tokens', 0.0)}% "
        f"cost={imp.get('cost_usd', 0.0)}% "
        f"paired={paired_count} rows={rows_total}"
    )
    print(line)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CodeGraph effectiveness tracker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_log = sub.add_parser("log", help="Log one A/B run")
    p_log.add_argument("--task-id", required=True, help="Stable task ID for pairing, e.g. arch-001")
    p_log.add_argument("--task-type", default="", help="Optional task category")
    p_log.add_argument("--mode", required=True, choices=["with", "without"], help="with=CodeGraph on, without=off")
    p_log.add_argument("--duration-sec", required=True, type=float)
    p_log.add_argument("--discovery-calls", required=True, type=int)
    p_log.add_argument("--tokens", required=True, type=int)
    p_log.add_argument("--cost-usd", required=True, type=float)
    p_log.add_argument("--impact-precision", type=float, default=None)
    p_log.add_argument("--impact-recall", type=float, default=None)
    p_log.add_argument("--notes", default="")
    p_log.set_defaults(func=cmd_log)

    p_summary = sub.add_parser("summary", help="Summarize A/B runs")
    p_summary.add_argument("--window-days", type=int, default=14)
    p_summary.add_argument("--write", action="store_true", help="Write summary_latest.json and summary_latest.md")
    p_summary.set_defaults(func=cmd_summary)

    p_kpi = sub.add_parser("kpi", help="Print compact one-line KPI summary")
    p_kpi.add_argument("--window-days", type=int, default=14)
    p_kpi.set_defaults(func=cmd_kpi)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
