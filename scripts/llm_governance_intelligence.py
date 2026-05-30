#!/usr/bin/env python3
"""Build an LLM governance intelligence report from real execution logs.

This report is intended to close the gap between static routing policy and
observed operational behavior. It summarizes:
- field coverage of canonical governance telemetry
- provider/model usage and outcome rates
- task/outcome rollups
- schema drift and policy update recommendations
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
WORKFLOW_LOG = REPO / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"
AGENT_LOG = REPO / "07_LOGS_AND_AUDIT" / "AGENT_RUN_LOG.jsonl"
ROUTING_DIR = REPO / "07_LOGS_AND_AUDIT" / "routing"
OUT_DIR = REPO / "07_LOGS_AND_AUDIT" / "governance_intelligence"

CANONICAL_FIELDS = [
    "timestamp",
    "task_id",
    "provider",
    "model",
    "task_type",
    "execution_status",
    "confidence_score",
    "cost_usd",
    "latency_ms",
]

SUCCESS_TERMS = {
    "ok",
    "success",
    "succeeded",
    "pass",
    "approved",
    "execute",
    "complete",
    "completed",
}
FAIL_TERMS = {
    "fail",
    "failed",
    "error",
    "halt",
    "halted",
    "blocked",
    "timeout",
    "timed_out",
    "denied",
    "rejected",
}


@dataclass
class NormalizedEvent:
    source: str
    raw_keys: list[str]
    timestamp: str | None
    task_id: str | None
    provider: str | None
    model: str | None
    task_type: str | None
    execution_status: str | None
    confidence_score: float | None
    cost_usd: float | None
    latency_ms: float | None


def _read_jsonl(path: Path, max_lines: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        if i >= max_lines:
            break
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _read_routing_jsonl(max_lines: int, max_files: int = 14) -> tuple[list[dict[str, Any]], list[str]]:
    if not ROUTING_DIR.is_dir():
        return [], []
    files = sorted(ROUTING_DIR.glob("routes_*.jsonl"), reverse=True)[:max_files]
    merged: list[dict[str, Any]] = []
    names: list[str] = []
    for path in files:
        if len(merged) >= max_lines:
            break
        remaining = max_lines - len(merged)
        rows = _read_jsonl(path, remaining)
        if rows:
            merged.extend(rows)
            names.append(str(path.relative_to(REPO)).replace("\\", "/"))
    return merged, names


def _pick(d: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in d and d[key] not in (None, ""):
            return d[key]
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize(source: str, row: dict[str, Any]) -> NormalizedEvent:
    confidence = _pick(row, "confidence_score")
    if confidence is None:
        conf_obj = row.get("confidence")
        if isinstance(conf_obj, dict):
            confidence = _pick(conf_obj, "score", "confidence_score")

    cost = _pick(row, "actual_cost", "estimated_cost", "cost_usd")
    latency = _pick(row, "latency_ms", "duration_ms", "elapsed_ms")

    provider = _pick(row, "provider", "selected_provider")
    model = _pick(row, "model", "selected_model", "assigned_model")
    if provider and not model:
        model = f"{provider}:default"

    return NormalizedEvent(
        source=source,
        raw_keys=sorted(row.keys()),
        timestamp=_pick(row, "timestamp", "generated_at", "created_at"),
        task_id=_pick(row, "task_id", "bead_id", "workflow_id", "request_id"),
        provider=provider,
        model=model,
        task_type=_pick(row, "task_type", "mode", "event_type"),
        execution_status=_pick(row, "result_status", "status", "result", "decision", "validation"),
        confidence_score=_to_float(confidence),
        cost_usd=_to_float(cost),
        latency_ms=_to_float(latency),
    )


def _status_bucket(value: str | None) -> str:
    if not value:
        return "unknown"
    text = value.strip().lower().replace(" ", "_")
    if text in SUCCESS_TERMS:
        return "success"
    if text in FAIL_TERMS:
        return "fail"
    if any(term in text for term in SUCCESS_TERMS):
        return "success"
    if any(term in text for term in FAIL_TERMS):
        return "fail"
    return "unknown"


def _coverage(events: list[NormalizedEvent]) -> dict[str, dict[str, float]]:
    total = max(len(events), 1)
    out: dict[str, dict[str, float]] = {}
    for field in CANONICAL_FIELDS:
        present = sum(1 for ev in events if getattr(ev, field) not in (None, ""))
        out[field] = {
            "present": present,
            "missing": len(events) - present,
            "coverage": round(present / total, 4),
        }
    return out


def _provider_model_rollup(events: list[NormalizedEvent]) -> dict[str, Any]:
    by_provider: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}

    for ev in events:
        status = _status_bucket(ev.execution_status)
        provider = ev.provider or "unknown"
        model = ev.model or "unknown"

        p = by_provider.setdefault(provider, {"events": 0, "success": 0, "fail": 0, "unknown": 0, "models": Counter()})
        p["events"] += 1
        p[status] += 1
        p["models"][model] += 1

        m = by_model.setdefault(model, {"events": 0, "success": 0, "fail": 0, "unknown": 0, "providers": Counter()})
        m["events"] += 1
        m[status] += 1
        m["providers"][provider] += 1

    # make JSON serializable
    for data in by_provider.values():
        data["models"] = dict(data["models"])
    for data in by_model.values():
        data["providers"] = dict(data["providers"])

    return {"providers": by_provider, "models": by_model}


def _task_rollup(events: list[NormalizedEvent]) -> dict[str, Any]:
    by_task: dict[str, dict[str, Any]] = {}
    for ev in events:
        if not ev.task_id:
            continue
        row = by_task.setdefault(
            ev.task_id,
            {
                "events": 0,
                "success": 0,
                "fail": 0,
                "unknown": 0,
                "providers": Counter(),
                "models": Counter(),
                "task_types": Counter(),
                "latest_timestamp": None,
                "latest_status": None,
            },
        )
        status = _status_bucket(ev.execution_status)
        row["events"] += 1
        row[status] += 1
        row["providers"][ev.provider or "unknown"] += 1
        row["models"][ev.model or "unknown"] += 1
        row["task_types"][ev.task_type or "unknown"] += 1
        if ev.timestamp and (row["latest_timestamp"] is None or str(ev.timestamp) > str(row["latest_timestamp"])):
            row["latest_timestamp"] = ev.timestamp
            row["latest_status"] = ev.execution_status

    for row in by_task.values():
        row["providers"] = dict(row["providers"])
        row["models"] = dict(row["models"])
        row["task_types"] = dict(row["task_types"])

    top_tasks = sorted(by_task.items(), key=lambda x: x[1]["events"], reverse=True)[:20]
    return {
        "task_count": len(by_task),
        "top_tasks": [{"task_id": tid, **data} for tid, data in top_tasks],
    }


def _schema_drift(events: list[NormalizedEvent]) -> dict[str, Any]:
    key_counts = Counter()
    for ev in events:
        key_counts.update(ev.raw_keys)
    total = max(len(events), 1)
    common = [
        {"key": k, "present": v, "coverage": round(v / total, 4)}
        for k, v in key_counts.most_common(30)
    ]
    return {"top_keys": common}


def _recommendations(coverage: dict[str, dict[str, float]]) -> list[str]:
    recs: list[str] = []
    for field, stats in coverage.items():
        c = stats["coverage"]
        if c < 0.25:
            recs.append(f"Critical telemetry gap: {field} coverage is {c:.0%}. Add mandatory logging in adapter + workflow emitters.")
        elif c < 0.6:
            recs.append(f"Improve telemetry: {field} coverage is {c:.0%}. Standardize this field in run-log schema.")
    if not recs:
        recs.append("Telemetry coverage is healthy for tracked canonical fields.")
    return recs


def build_report(max_lines: int) -> dict[str, Any]:
    workflow_rows = _read_jsonl(WORKFLOW_LOG, max_lines=max_lines)
    agent_rows = _read_jsonl(AGENT_LOG, max_lines=max_lines)
    routing_rows, routing_files = _read_routing_jsonl(max_lines=max_lines)

    events: list[NormalizedEvent] = []
    events.extend(_normalize("workflow", row) for row in workflow_rows)
    events.extend(_normalize("agent", row) for row in agent_rows)
    events.extend(_normalize("routing", row) for row in routing_rows)

    coverage = _coverage(events)
    provider_model = _provider_model_rollup(events)
    task = _task_rollup(events)
    schema = _schema_drift(events)

    return {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "workflow_log": {
                "path": str(WORKFLOW_LOG.relative_to(REPO)).replace("\\", "/"),
                "rows": len(workflow_rows),
            },
            "agent_log": {
                "path": str(AGENT_LOG.relative_to(REPO)).replace("\\", "/"),
                "rows": len(agent_rows),
            },
            "routing_logs": {
                "files": routing_files,
                "rows": len(routing_rows),
            },
        },
        "event_count": len(events),
        "canonical_coverage": coverage,
        "provider_model_rollup": provider_model,
        "task_rollup": task,
        "schema_drift": schema,
        "recommendations": _recommendations(coverage),
    }


def _write_report(report: dict[str, Any]) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_json = OUT_DIR / f"governance_intelligence_{ts}.json"
    latest_json = OUT_DIR / "latest.json"
    latest_md = OUT_DIR / "latest.md"
    history_jsonl = OUT_DIR / "history.jsonl"

    run_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with history_jsonl.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report) + "\n")

    lines: list[str] = []
    lines.append("# LLM Governance Intelligence")
    lines.append("")
    lines.append(f"Generated: {report.get('generated_at','')}")
    lines.append(f"Event count: {report.get('event_count', 0)}")
    lines.append("")
    lines.append("## Canonical Coverage")
    lines.append("")
    for field, stats in report.get("canonical_coverage", {}).items():
        lines.append(f"- {field}: {stats.get('coverage', 0.0):.0%} ({stats.get('present', 0)}/{stats.get('present', 0) + stats.get('missing', 0)})")

    lines.append("")
    lines.append("## Top Providers")
    lines.append("")
    provider_items = report.get("provider_model_rollup", {}).get("providers", {})
    sorted_providers = sorted(provider_items.items(), key=lambda x: x[1].get("events", 0), reverse=True)[:10]
    if not sorted_providers:
        lines.append("- No provider telemetry found.")
    for name, data in sorted_providers:
        lines.append(
            f"- {name}: events={data.get('events',0)}, success={data.get('success',0)}, fail={data.get('fail',0)}, unknown={data.get('unknown',0)}"
        )

    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    for rec in report.get("recommendations", []):
        lines.append(f"- {rec}")

    latest_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "run_json": str(run_json.relative_to(REPO)).replace("\\", "/"),
        "latest_json": str(latest_json.relative_to(REPO)).replace("\\", "/"),
        "latest_md": str(latest_md.relative_to(REPO)).replace("\\", "/"),
        "history_jsonl": str(history_jsonl.relative_to(REPO)).replace("\\", "/"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM governance intelligence report from run logs")
    parser.add_argument("--max-lines", type=int, default=5000)
    parser.add_argument("--write", action="store_true", help="Write reports under 07_LOGS_AND_AUDIT/governance_intelligence")
    args = parser.parse_args()

    report = build_report(max_lines=max(1, args.max_lines))
    if args.write:
        report["artifacts"] = _write_report(report)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
