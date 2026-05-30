#!/usr/bin/env python3
"""Generate a compact harness health snapshot for new-session readiness and KPI quality."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
LOGS = REPO / "07_LOGS_AND_AUDIT"
OUT_DIR = LOGS / "harness_health"
OUT_JSON = OUT_DIR / "latest.json"
OUT_MD = OUT_DIR / "latest.md"

UNIFIED_GUARD = LOGS / "unified_guard" / "latest.json"
PRE_SESSION = LOGS / "pre_session" / "latest.json"
TOKEN_GOV = LOGS / "token_governance" / "latest.json"
GOV_INTEL = LOGS / "governance_intelligence" / "latest.json"
AGENT_LOG = LOGS / "AGENT_RUN_LOG.jsonl"
CG_SCORECARD = LOGS / "codegraph_effectiveness" / "summary_latest.json"
BUDGET_FORECAST = LOGS / "budget" / "forecast_latest.json"
BUDGET_ACCURACY = LOGS / "budget" / "forecast_accuracy_latest.json"
BUDGET_CHANNEL_TREND = LOGS / "budget" / "forecast_channel_trend_latest.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _file_fresh(path: Path, max_age_minutes: int) -> tuple[bool, float | None]:
    if not path.is_file():
        return False, None
    age = _utc_now() - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age_minutes = round(age.total_seconds() / 60.0, 2)
    return age <= timedelta(minutes=max_age_minutes), age_minutes


def _line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


@dataclass
class Check:
    name: str
    status: str
    message: str
    value: Any | None = None


def _add_check(checks: list[Check], name: str, passed: bool, message: str, value: Any | None = None, warn: bool = False) -> None:
    status = "pass" if passed else ("warn" if warn else "fail")
    checks.append(Check(name=name, status=status, message=message, value=value))


def _coverage(source: dict[str, Any], key: str) -> float:
    return float((((source.get("canonical_coverage") or {}).get(key) or {}).get("coverage") or 0.0))


def _coverage_llm_applicable(source: dict[str, Any], key: str) -> tuple[float, int]:
    llm_cov = (((source.get("canonical_coverage_llm_applicable") or {}).get("coverage") or {}).get(key) or {})
    value = llm_cov.get("coverage")
    if value is None:
        return _coverage(source, key), 0
    count = int(((source.get("canonical_coverage_llm_applicable") or {}).get("event_count") or 0))
    return float(value), count


def _build_markdown(snapshot: dict[str, Any]) -> str:
    checks = snapshot.get("checks") or []
    lines = [
        "# Harness Health Snapshot",
        "",
        f"- generated_at_utc: {snapshot.get('generated_at_utc', '')}",
        f"- overall_status: {snapshot.get('overall_status', 'unknown')}",
        f"- readiness_score: {snapshot.get('readiness_score', 0)}/100",
        "",
        "## Check Results",
        "",
        "| Check | Status | Message |",
        "|---|---|---|",
    ]
    for c in checks:
        lines.append(f"| {c.get('name','')} | {c.get('status','')} | {c.get('message','')} |")

    lines.extend(
        [
            "",
            "## Coverage",
            "",
            f"- provider: {snapshot.get('coverage', {}).get('provider', 0.0)}",
            f"- model: {snapshot.get('coverage', {}).get('model', 0.0)}",
            f"- task_id: {snapshot.get('coverage', {}).get('task_id', 0.0)}",
            f"- execution_status: {snapshot.get('coverage', {}).get('execution_status', 0.0)}",
            f"- confidence_score: {snapshot.get('coverage', {}).get('confidence_score', 0.0)}",
            f"- cost_usd: {snapshot.get('coverage', {}).get('cost_usd', 0.0)}",
            f"- latency_ms: {snapshot.get('coverage', {}).get('latency_ms', 0.0)}",
            "",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate harness readiness + KPI health snapshot")
    parser.add_argument("--write", action="store_true", help="Write 07_LOGS_AND_AUDIT/harness_health/latest.{json,md}")
    parser.add_argument("--max-pre-session-age-min", type=int, default=360)
    parser.add_argument("--max-unified-guard-age-min", type=int, default=30)
    parser.add_argument("--max-agent-log-age-min", type=int, default=1440)
    parser.add_argument("--min-agent-log-lines", type=int, default=1)
    parser.add_argument("--min-cg-paired", type=int, default=10)
    args = parser.parse_args()

    unified = _read_json(UNIFIED_GUARD)
    pre = _read_json(PRE_SESSION)
    token = _read_json(TOKEN_GOV)
    intel = _read_json(GOV_INTEL)
    cg = _read_json(CG_SCORECARD)
    forecast = _read_json(BUDGET_FORECAST)
    forecast_accuracy = _read_json(BUDGET_ACCURACY)
    channel_trend = _read_json(BUDGET_CHANNEL_TREND)

    checks: list[Check] = []

    unified_ok = bool(unified.get("ok") is True)
    _add_check(checks, "unified_guard_ok", unified_ok, f"ok={unified.get('ok')}")

    token_status = str(token.get("status") or "unknown").lower()
    token_ok = token_status == "green"
    _add_check(checks, "token_governance_green", token_ok, f"status={token_status}")

    pre_fresh, pre_age = _file_fresh(PRE_SESSION, args.max_pre_session_age_min)
    _add_check(checks, "pre_session_fresh", pre_fresh, f"age_min={pre_age}", value=pre_age)

    ug_fresh, ug_age = _file_fresh(UNIFIED_GUARD, args.max_unified_guard_age_min)
    _add_check(checks, "unified_guard_fresh", ug_fresh, f"age_min={ug_age}", value=ug_age)

    handoff_present = bool(pre.get("handoff_present") is True)
    _add_check(checks, "handoff_present", handoff_present, f"handoff_present={handoff_present}")

    mcp_over = bool(((pre.get("mcp_audit") or {}).get("over_warn_threshold") is True))
    _add_check(checks, "mcp_budget", not mcp_over, f"over_warn_threshold={mcp_over}")

    # Telemetry completeness checks (soft warning for confidence/cost/latency).
    cov_provider, llm_cov_events = _coverage_llm_applicable(intel, "provider")
    cov_model, _ = _coverage_llm_applicable(intel, "model")
    cov_task, _ = _coverage_llm_applicable(intel, "task_id")
    cov_exec, _ = _coverage_llm_applicable(intel, "execution_status")
    cov_conf, _ = _coverage_llm_applicable(intel, "confidence_score")
    cov_cost, _ = _coverage_llm_applicable(intel, "cost_usd")
    cov_lat, _ = _coverage_llm_applicable(intel, "latency_ms")

    provider_model_soft = cov_provider >= 0.9 and cov_model >= 0.9
    provider_model_hard = cov_provider >= 0.5 and cov_model >= 0.5
    _add_check(
        checks,
        "coverage_provider_model",
        provider_model_soft,
        f"provider={cov_provider} model={cov_model} llm_events={llm_cov_events}",
        warn=provider_model_hard and not provider_model_soft,
    )

    task_exec_soft = cov_task >= 0.9 and cov_exec >= 0.9
    task_exec_hard = cov_task >= 0.7 and cov_exec >= 0.7
    _add_check(
        checks,
        "coverage_task_exec",
        task_exec_soft,
        f"task_id={cov_task} execution_status={cov_exec} llm_events={llm_cov_events}",
        warn=task_exec_hard and not task_exec_soft,
    )
    _add_check(
        checks,
        "coverage_confidence_cost_latency",
        cov_conf >= 0.9 and cov_cost >= 0.9 and cov_lat >= 0.9,
        f"confidence={cov_conf} cost={cov_cost} latency={cov_lat}",
        warn=(cov_conf >= 0.7 and cov_cost >= 0.7 and cov_lat >= 0.7),
    )

    agent_fresh, agent_age = _file_fresh(AGENT_LOG, args.max_agent_log_age_min)
    agent_lines = _line_count(AGENT_LOG)
    _add_check(
        checks,
        "agent_log_fresh_and_populated",
        bool(agent_fresh and agent_lines >= args.min_agent_log_lines),
        f"age_min={agent_age} lines={agent_lines}",
        value={"age_min": agent_age, "lines": agent_lines},
        warn=True,
    )

    paired_count = int(cg.get("paired_count") or 0)
    codegraph_pass = paired_count >= 1
    codegraph_warn = paired_count > 0 and paired_count < args.min_cg_paired
    _add_check(
        checks,
        "codegraph_sample_size",
        codegraph_pass,
        f"paired_count={paired_count}",
        value=paired_count,
        warn=codegraph_warn,
    )

    weekly = ((forecast.get("limits") or {}).get("weekly") or {}) if isinstance(forecast, dict) else {}
    forecast_ready = isinstance(weekly, dict) and bool(weekly)
    _add_check(
        checks,
        "budget_forecast_present",
        forecast_ready,
        "forecast artifact loaded" if forecast_ready else "forecast artifact missing",
        warn=not forecast_ready,
    )

    optimization_state = str(weekly.get("optimization_state") or "unknown") if forecast_ready else "unknown"
    gap_to_target = float(
        weekly.get("forecast_gap_to_target_usd", weekly.get("forecast_gap_to_90_pct_target_usd") or 0.0)
    ) if forecast_ready else 0.0
    need_per_day = float(
        weekly.get("daily_spend_needed_to_hit_target_usd", weekly.get("daily_spend_needed_to_hit_90_pct_usd") or 0.0)
    ) if forecast_ready else 0.0
    target_pct = float(weekly.get("target_utilization_pct") or 90.0) if forecast_ready else 90.0
    _add_check(
        checks,
        "weekly_budget_optimization",
        optimization_state == "at_or_above_target",
        f"state={optimization_state} target_pct={round(target_pct, 2)} gap_target_usd={round(gap_to_target, 4)} need_per_day_usd={round(need_per_day, 4)}",
        value={
            "optimization_state": optimization_state,
            "target_utilization_pct": round(target_pct, 4),
            "forecast_gap_to_target_usd": round(gap_to_target, 4),
            "daily_spend_needed_to_hit_target_usd": round(need_per_day, 4),
        },
        warn=optimization_state in {"below_target", "unknown"},
    )

    accuracy_present = bool(forecast_accuracy)
    _add_check(
        checks,
        "forecast_accuracy_present",
        accuracy_present,
        "accuracy artifact loaded" if accuracy_present else "accuracy artifact missing",
        warn=not accuracy_present,
    )
    acc_status = str(forecast_accuracy.get("status") or "unknown") if accuracy_present else "unknown"
    week_mape = float((((forecast_accuracy.get("metrics") or {}).get("week") or {}).get("mape_pct") or 0.0)) if accuracy_present else 0.0
    _add_check(
        checks,
        "forecast_accuracy_weekly",
        acc_status == "green" and week_mape <= 35.0,
        f"status={acc_status} week_mape_pct={round(week_mape, 2)}",
        value={"status": acc_status, "week_mape_pct": round(week_mape, 2)},
        warn=acc_status in {"yellow", "unknown"} or (week_mape > 35.0 and week_mape <= 55.0),
    )

    channels = forecast.get("channels") if isinstance(forecast.get("channels"), dict) else {}
    vscode_week = float(((channels.get("vscode") or {}).get("weekly_spent_usd") or 0.0))
    cursor_week = float(((channels.get("cursor") or {}).get("weekly_spent_usd") or 0.0))
    _add_check(
        checks,
        "budget_channels_present",
        bool(channels),
        f"channels={len(channels)} vscode_week={round(vscode_week, 4)} cursor_week={round(cursor_week, 4)}",
        value={"channels": len(channels), "vscode_week": round(vscode_week, 4), "cursor_week": round(cursor_week, 4)},
        warn=not bool(channels),
    )

    trend_present = bool(channel_trend)
    _add_check(
        checks,
        "forecast_channel_trend_present",
        trend_present,
        "trend artifact loaded" if trend_present else "trend artifact missing",
        warn=not trend_present,
    )
    trend_status = str(channel_trend.get("status") or "unknown") if trend_present else "unknown"
    _add_check(
        checks,
        "forecast_channel_trend_status",
        trend_status == "green",
        f"status={trend_status}",
        value={"status": trend_status},
        warn=trend_status == "yellow" or trend_status == "unknown",
    )

    fail_count = sum(1 for c in checks if c.status == "fail")
    warn_count = sum(1 for c in checks if c.status == "warn")
    pass_count = sum(1 for c in checks if c.status == "pass")

    hard_fail_names = {
        "unified_guard_ok",
        "token_governance_green",
        "pre_session_fresh",
        "unified_guard_fresh",
        "handoff_present",
        "mcp_budget",
        "coverage_provider_model",
        "coverage_task_exec",
    }
    hard_fail = any(c.status == "fail" and c.name in hard_fail_names for c in checks)

    readiness_score = max(0, 100 - (fail_count * 20) - (warn_count * 8))
    overall_status = "red" if hard_fail else ("yellow" if warn_count > 0 else "green")

    snapshot = {
        "generated_at_utc": _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overall_status": overall_status,
        "readiness_score": readiness_score,
        "counts": {"pass": pass_count, "warn": warn_count, "fail": fail_count},
        "checks": [
            {"name": c.name, "status": c.status, "message": c.message, "value": c.value}
            for c in checks
        ],
        "coverage": {
            "provider": cov_provider,
            "model": cov_model,
            "task_id": cov_task,
            "execution_status": cov_exec,
            "confidence_score": cov_conf,
            "cost_usd": cov_cost,
            "latency_ms": cov_lat,
            "llm_applicable_event_count": llm_cov_events,
        },
        "inputs": {
            "unified_guard": str(UNIFIED_GUARD.relative_to(REPO)),
            "pre_session": str(PRE_SESSION.relative_to(REPO)),
            "token_governance": str(TOKEN_GOV.relative_to(REPO)),
            "governance_intelligence": str(GOV_INTEL.relative_to(REPO)),
            "agent_log": str(AGENT_LOG.relative_to(REPO)),
            "codegraph_scorecard": str(CG_SCORECARD.relative_to(REPO)),
            "budget_forecast": str(BUDGET_FORECAST.relative_to(REPO)),
            "budget_forecast_accuracy": str(BUDGET_ACCURACY.relative_to(REPO)),
            "budget_channel_trend": str(BUDGET_CHANNEL_TREND.relative_to(REPO)),
        },
        "budget_weekly": {
            "current_usd": weekly.get("current_usd") if forecast_ready else None,
            "cap_usd": weekly.get("cap_usd") if forecast_ready else None,
            "remaining_usd": weekly.get("remaining_usd") if forecast_ready else None,
            "forecast_remaining_usd": weekly.get("forecast_remaining_usd") if forecast_ready else None,
            "target_utilization_pct": weekly.get("target_utilization_pct") if forecast_ready else None,
            "target_utilization_usd": weekly.get("target_utilization_usd") if forecast_ready else None,
            "forecast_gap_to_target_usd": weekly.get("forecast_gap_to_target_usd") if forecast_ready else None,
            "daily_spend_needed_to_hit_target_usd": weekly.get("daily_spend_needed_to_hit_target_usd") if forecast_ready else None,
            "optimization_state": optimization_state,
        },
        "forecast_accuracy": {
            "status": acc_status,
            "week_mape_pct": round(week_mape, 2),
            "coverage": forecast_accuracy.get("coverage") if accuracy_present else None,
        },
        "budget_channels": channels if channels else None,
        "forecast_accuracy_channels": (forecast_accuracy.get("channels") if accuracy_present else None),
        "forecast_accuracy_channel_trend": channel_trend if trend_present else None,
    }

    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        OUT_MD.write_text(_build_markdown(snapshot), encoding="utf-8")

    print(json.dumps(snapshot, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
