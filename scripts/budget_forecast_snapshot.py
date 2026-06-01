#!/usr/bin/env python3
"""Build budget usage + forecast snapshot for statusline and session hooks.

Outputs a JSON snapshot with:
- boot estimate (from pre_session manifest)
- burn/current usage across session/daily/weekly/monthly scopes
- forecasted end-of-day/week/month spend using trailing burn rate
- provider/model usage rollups from governance intelligence
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "07_LOGS_AND_AUDIT" / "budget" / "forecast_latest.json"
HISTORY_OUT = REPO / "07_LOGS_AND_AUDIT" / "budget" / "forecast_history.jsonl"
CHANNEL_KEYS = ("vscode", "cursor", "claude_code", "codex", "cli", "other")


def _load_budget_config() -> dict[str, Any]:
    cfg_path = REPO / "config" / "agent_budget.yaml"
    if not cfg_path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _load_caps(cfg: dict[str, Any] | None = None) -> dict[str, float]:
    caps = {
        "session_tokens": 200_000.0,
        "daily_usd": 25.0,
        "weekly_usd": 100.0,
        "monthly_usd": 400.0,
    }
    config = cfg or _load_budget_config()

    raw_caps = config.get("caps") or {}
    try:
        caps["session_tokens"] = float(raw_caps.get("session_tokens", caps["session_tokens"]))
        caps["daily_usd"] = float(raw_caps.get("daily_usd", caps["daily_usd"]))
        caps["monthly_usd"] = float(raw_caps.get("monthly_usd", caps["monthly_usd"]))
        # Optional explicit weekly cap; fallback to monthly/4 if absent.
        caps["weekly_usd"] = float(raw_caps.get("weekly_usd", caps["monthly_usd"] / 4.0))
    except (TypeError, ValueError):
        return caps
    return caps


def _load_optimization_policy(cfg: dict[str, Any] | None = None) -> dict[str, float]:
    config = cfg or _load_budget_config()
    raw = (config.get("optimization") or {}) if isinstance(config, dict) else {}

    def _num(key: str, default: float) -> float:
        try:
            return float(raw.get(key, default))
        except (TypeError, ValueError):
            return default

    policy = {
        "target_default_pct": _num("weekly_target_utilization_pct_default", 90.0),
        "target_min_pct": _num("weekly_target_utilization_pct_min", 70.0),
        "target_max_pct": _num("weekly_target_utilization_pct_max", 95.0),
        "lower_on_unknown_warning_pct": _num("lower_target_when_unknown_usage_warning_pct", 10.0),
        "lower_on_risk_red_pct": _num("lower_target_when_risk_red_pct", 5.0),
        "lower_on_risk_yellow_pct": _num("lower_target_when_risk_yellow_pct", 2.0),
    }
    if policy["target_min_pct"] > policy["target_max_pct"]:
        policy["target_min_pct"], policy["target_max_pct"] = policy["target_max_pct"], policy["target_min_pct"]
    return policy


def _load_channel_caps(cfg: dict[str, Any] | None, global_caps: dict[str, float]) -> dict[str, dict[str, float]]:
    config = cfg or _load_budget_config()
    raw = (config.get("channel_caps") or {}) if isinstance(config, dict) else {}
    out: dict[str, dict[str, float]] = {}
    for key in CHANNEL_KEYS:
        c = raw.get(key) if isinstance(raw.get(key), dict) else {}
        try:
            daily = float(c.get("daily_usd", global_caps["daily_usd"]))
            weekly = float(c.get("weekly_usd", global_caps["weekly_usd"]))
            monthly = float(c.get("monthly_usd", global_caps["monthly_usd"]))
        except (TypeError, ValueError):
            daily = float(global_caps["daily_usd"])
            weekly = float(global_caps["weekly_usd"])
            monthly = float(global_caps["monthly_usd"])
        out[key] = {
            "daily_usd": max(0.0, daily),
            "weekly_usd": max(0.0, weekly),
            "monthly_usd": max(0.0, monthly),
        }
    return out


def _load_daily_entries() -> list[dict[str, Any]]:
    path = REPO / "07_LOGS_AND_AUDIT" / "budget" / "daily.jsonl"
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        return []
    return rows


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _sum_since(rows: list[dict[str, Any]], cutoff: datetime) -> float:
    total = 0.0
    for row in rows:
        ts = _parse_ts(row.get("timestamp"))
        if ts is None or ts < cutoff:
            continue
        try:
            total += float(row.get("amount_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
    return total


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


def _filter_channel(rows: list[dict[str, Any]], channel: str) -> list[dict[str, Any]]:
    return [row for row in rows if _normalize_channel(row) == channel]


def _sum_same_prefix(rows: list[dict[str, Any]], prefix: str) -> float:
    total = 0.0
    for row in rows:
        ts = str(row.get("timestamp", ""))
        if not ts.startswith(prefix):
            continue
        try:
            total += float(row.get("amount_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
    return total


def _daily_totals(rows: list[dict[str, Any]], *, now_utc: datetime, days: int = 7) -> list[float]:
    """Return daily totals for trailing N calendar days (oldest -> newest)."""
    by_day: dict[str, float] = {}
    for row in rows:
        ts = _parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        key = ts.strftime("%Y-%m-%d")
        try:
            by_day[key] = by_day.get(key, 0.0) + float(row.get("amount_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue

    out: list[float] = []
    day_cursor = now_utc.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
    for _ in range(days):
        out.append(round(by_day.get(day_cursor.strftime("%Y-%m-%d"), 0.0), 4))
        day_cursor += timedelta(days=1)
    return out


def _weekly_trend_pct(rows: list[dict[str, Any]], *, now_utc: datetime) -> float:
    """Trend as pct delta between recent 3-day avg and previous 3-day avg."""
    totals = _daily_totals(rows, now_utc=now_utc, days=7)
    prev = totals[0:3]
    recent = totals[3:6]
    prev_avg = sum(prev) / 3.0 if prev else 0.0
    recent_avg = sum(recent) / 3.0 if recent else 0.0
    if prev_avg <= 1e-9:
        if recent_avg <= 1e-9:
            return 0.0
        return 100.0
    return round(((recent_avg - prev_avg) / prev_avg) * 100.0, 2)


def _top_from_rollup(data: dict[str, Any], key: str) -> dict[str, Any]:
    items = data.get(key)
    if not isinstance(items, dict) or not items:
        return {"name": "unknown", "events": 0, "success_rate": 0.0}
    ranked: list[tuple[str, dict[str, Any], int]] = []
    for name, row in items.items():
        if not isinstance(row, dict):
            continue
        events = int(row.get("events", 0) or 0)
        ranked.append((str(name), row, events))

    if not ranked:
        return {"name": "unknown", "events": 0, "success_rate": 0.0}

    ranked.sort(key=lambda entry: entry[2], reverse=True)
    pick_name, pick_row, pick_events = ranked[0]
    for name, row, events in ranked:
        if name.lower() not in {"unknown", "route_blocked", "none", "null", ""}:
            pick_name, pick_row, pick_events = name, row, events
            break
    denom = int(pick_row.get("events", 0) or 0)
    success = int(pick_row.get("success", 0) or 0)
    rate = round(success / denom, 4) if denom > 0 else 0.0
    return {"name": pick_name, "events": max(0, pick_events), "success_rate": rate}


def _provider_burn_breakdown(
    providers: dict[str, Any],
    *,
    daily_spent: float,
    weekly_spent: float,
    monthly_spent: float,
    limit: int = 8,
) -> list[dict[str, Any]]:
    rows: list[tuple[str, int]] = []
    for name, value in providers.items():
        if not isinstance(value, dict):
            continue
        events = int(value.get("events", 0) or 0)
        if events <= 0:
            continue
        rows.append((str(name), events))

    if not rows:
        return []

    rows.sort(key=lambda item: item[1], reverse=True)
    rows = rows[:limit]
    total_events = sum(events for _, events in rows)
    if total_events <= 0:
        return []

    breakdown: list[dict[str, Any]] = []
    for name, events in rows:
        share = events / total_events
        breakdown.append(
            {
                "provider": name,
                "events": events,
                "event_share": round(share, 4),
                "estimated_daily_usd": round(daily_spent * share, 4),
                "estimated_weekly_usd": round(weekly_spent * share, 4),
                "estimated_monthly_usd": round(monthly_spent * share, 4),
            }
        )
    return breakdown


def _unknown_usage_share(providers: dict[str, Any]) -> dict[str, Any]:
    unknown_keys = {"unknown", "route_blocked", "none", "null", ""}
    total_events = 0
    unknown_events = 0
    for name, value in providers.items():
        if not isinstance(value, dict):
            continue
        events = int(value.get("events", 0) or 0)
        total_events += events
        if str(name).lower() in unknown_keys:
            unknown_events += events
    share = (unknown_events / total_events) if total_events > 0 else 0.0
    return {
        "unknown_events": unknown_events,
        "total_events": total_events,
        "unknown_share": round(share, 4),
        "warning": total_events >= 50 and share >= 0.5,
    }


def build_snapshot(now: datetime | None = None) -> dict[str, Any]:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    config = _load_budget_config()
    caps = _load_caps(config)
    channel_caps = _load_channel_caps(config, caps)
    optimization_policy = _load_optimization_policy(config)

    pre = _read_json(REPO / "07_LOGS_AND_AUDIT" / "pre_session" / "latest.json")
    mcp = pre.get("mcp_audit") if isinstance(pre.get("mcp_audit"), dict) else {}
    boot_tokens = int(mcp.get("estimated_tokens_if_enabled") or 0)
    session_cap = int(caps["session_tokens"])
    session_remaining = max(0, session_cap - boot_tokens)

    rows = _load_daily_entries()
    today_prefix = now_utc.strftime("%Y-%m-%d")
    month_prefix = now_utc.strftime("%Y-%m")
    day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=6)

    daily_spent = _sum_same_prefix(rows, today_prefix)
    weekly_spent = _sum_since(rows, week_start)
    monthly_spent = _sum_same_prefix(rows, month_prefix)
    weekly_trend_pct = _weekly_trend_pct(rows, now_utc=now_utc)

    trailing_days = max(1.0, (now_utc - week_start).total_seconds() / 86400.0)
    burn_rate_daily = weekly_spent / trailing_days

    hours_elapsed = max(1e-6, (now_utc - day_start).total_seconds() / 3600.0)
    hours_remaining_day = max(0.0, 24.0 - hours_elapsed)
    day_projection = daily_spent + burn_rate_daily * (hours_remaining_day / 24.0)

    days_elapsed_week = max(1.0, (now_utc - week_start).total_seconds() / 86400.0)
    days_remaining_week = max(0.0, 7.0 - days_elapsed_week)
    week_projection = weekly_spent + burn_rate_daily * days_remaining_week

    month_end = (now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0) + timedelta(days=32)).replace(day=1)
    days_remaining_month = max(0.0, (month_end - now_utc).total_seconds() / 86400.0)
    month_projection = monthly_spent + burn_rate_daily * days_remaining_month

    intel = _read_json(REPO / "07_LOGS_AND_AUDIT" / "governance_intelligence" / "latest.json")
    pm = intel.get("provider_model_rollup") if isinstance(intel.get("provider_model_rollup"), dict) else {}
    providers_rollup = pm.get("providers") if isinstance(pm.get("providers"), dict) else {}
    provider_top = _top_from_rollup(pm, "providers")
    model_top = _top_from_rollup(pm, "models")
    provider_breakdown = _provider_burn_breakdown(
        providers_rollup,
        daily_spent=daily_spent,
        weekly_spent=weekly_spent,
        monthly_spent=monthly_spent,
    )
    unknown_usage = _unknown_usage_share(providers_rollup)

    weekly_cap = float(caps["weekly_usd"])
    daily_cap = float(caps["daily_usd"])
    monthly_cap = float(caps["monthly_usd"])

    day_ratio = (day_projection / daily_cap) if daily_cap > 0 else 0.0
    week_ratio = (week_projection / weekly_cap) if weekly_cap > 0 else 0.0
    month_ratio = (month_projection / monthly_cap) if monthly_cap > 0 else 0.0
    max_ratio = max(day_ratio, week_ratio, month_ratio)

    if max_ratio >= 1.0:
        risk_level = "red"
    elif max_ratio >= 0.85:
        risk_level = "yellow"
    else:
        risk_level = "green"

    target_pct = optimization_policy["target_default_pct"]
    target_reasons: list[str] = [f"base={target_pct:.1f}%"]
    if unknown_usage.get("warning"):
        target_pct -= optimization_policy["lower_on_unknown_warning_pct"]
        target_reasons.append(
            f"-unknown_warning({optimization_policy['lower_on_unknown_warning_pct']:.1f}%)"
        )
    if risk_level == "red":
        target_pct -= optimization_policy["lower_on_risk_red_pct"]
        target_reasons.append(f"-risk_red({optimization_policy['lower_on_risk_red_pct']:.1f}%)")
    elif risk_level == "yellow":
        target_pct -= optimization_policy["lower_on_risk_yellow_pct"]
        target_reasons.append(f"-risk_yellow({optimization_policy['lower_on_risk_yellow_pct']:.1f}%)")

    target_pct = max(optimization_policy["target_min_pct"], min(optimization_policy["target_max_pct"], target_pct))
    if target_pct != optimization_policy["target_default_pct"]:
        target_reasons.append(f"bounded={target_pct:.1f}%")
    weekly_target_usd = weekly_cap * (target_pct / 100.0)

    weekly_remaining_actual = max(0.0, weekly_cap - weekly_spent)
    weekly_remaining_forecast = max(0.0, weekly_cap - week_projection)
    weekly_gap_to_target_actual = max(0.0, weekly_target_usd - weekly_spent)
    weekly_gap_to_target_forecast = max(0.0, weekly_target_usd - week_projection)
    days_remaining_calendar = max(1, int(math.ceil(days_remaining_week)))
    daily_needed_to_hit_target = (
        weekly_gap_to_target_forecast / float(days_remaining_calendar)
        if weekly_gap_to_target_forecast > 0 and days_remaining_calendar > 0
        else 0.0
    )
    weekly_optimization_state = (
        "below_target" if week_projection < weekly_target_usd else "at_or_above_target"
    )

    channel_rows: dict[str, list[dict[str, Any]]] = {
        key: _filter_channel(rows, key) for key in CHANNEL_KEYS
    }
    channels: dict[str, Any] = {}
    for key in CHANNEL_KEYS:
        c_rows = channel_rows[key]
        c_daily = _sum_same_prefix(c_rows, today_prefix)
        c_weekly = _sum_since(c_rows, week_start)
        c_monthly = _sum_same_prefix(c_rows, month_prefix)
        c_burn = c_weekly / trailing_days if trailing_days > 0 else 0.0
        c_day_projection = c_daily + c_burn * (hours_remaining_day / 24.0)
        c_week_projection = c_weekly + c_burn * days_remaining_week
        c_month_projection = c_monthly + c_burn * days_remaining_month

        c_caps = channel_caps.get(key) or {}
        c_daily_cap = float(c_caps.get("daily_usd", daily_cap) or daily_cap)
        c_weekly_cap = float(c_caps.get("weekly_usd", weekly_cap) or weekly_cap)
        c_monthly_cap = float(c_caps.get("monthly_usd", monthly_cap) or monthly_cap)
        c_day_ratio = (c_day_projection / c_daily_cap) if c_daily_cap > 0 else 0.0
        c_week_ratio = (c_week_projection / c_weekly_cap) if c_weekly_cap > 0 else 0.0
        c_month_ratio = (c_month_projection / c_monthly_cap) if c_monthly_cap > 0 else 0.0
        c_max_ratio = max(c_day_ratio, c_week_ratio, c_month_ratio)
        if c_max_ratio >= 1.0:
            c_risk = "red"
        elif c_max_ratio >= 0.85:
            c_risk = "yellow"
        else:
            c_risk = "green"

        c_target_usd = c_weekly_cap * (target_pct / 100.0)
        c_forecast_gap = max(0.0, c_target_usd - c_week_projection)
        c_need_per_day = (
            c_forecast_gap / float(days_remaining_calendar)
            if c_forecast_gap > 0 and days_remaining_calendar > 0
            else 0.0
        )
        channels[key] = {
            "daily_spent_usd": round(c_daily, 4),
            "weekly_spent_usd": round(c_weekly, 4),
            "monthly_spent_usd": round(c_monthly, 4),
            "end_of_day_usd": round(c_day_projection, 4),
            "end_of_week_usd": round(c_week_projection, 4),
            "end_of_month_usd": round(c_month_projection, 4),
            "weekly_spent_share": round((c_weekly / weekly_spent) if weekly_spent > 0 else 0.0, 4),
            "cap_daily_usd": round(c_daily_cap, 4),
            "cap_weekly_usd": round(c_weekly_cap, 4),
            "cap_monthly_usd": round(c_monthly_cap, 4),
            "daily_utilization_forecast": round(c_day_ratio, 4),
            "weekly_utilization_forecast": round(c_week_ratio, 4),
            "monthly_utilization_forecast": round(c_month_ratio, 4),
            "risk_level": c_risk,
            "target_utilization_pct": round(target_pct, 4),
            "target_utilization_usd": round(c_target_usd, 4),
            "forecast_gap_to_target_usd": round(c_forecast_gap, 4),
            "daily_spend_needed_to_hit_target_usd": round(c_need_per_day, 4),
            "optimization_state": "below_target" if c_week_projection < c_target_usd else "at_or_above_target",
        }

    return {
        "generated_at": now_utc.isoformat(),
        "boot": {
            "estimated_tokens": boot_tokens,
            "session_cap_tokens": session_cap,
            "session_remaining_tokens": session_remaining,
            "session_used_pct": round((boot_tokens / session_cap) if session_cap > 0 else 0.0, 4),
        },
        "burn": {
            "daily_spent_usd": round(daily_spent, 4),
            "weekly_spent_usd": round(weekly_spent, 4),
            "monthly_spent_usd": round(monthly_spent, 4),
            "daily_burn_rate_usd": round(burn_rate_daily, 4),
            "weekly_trend_pct": weekly_trend_pct,
        },
        "limits": {
            "daily": {
                "cap_usd": daily_cap,
                "current_usd": round(daily_spent, 4),
                "remaining_usd": round(max(0.0, daily_cap - daily_spent), 4),
            },
            "weekly": {
                "cap_usd": weekly_cap,
                "current_usd": round(weekly_spent, 4),
                "remaining_usd": round(max(0.0, weekly_cap - weekly_spent), 4),
                "forecast_remaining_usd": round(weekly_remaining_forecast, 4),
                "target_utilization_pct": round(target_pct, 4),
                "target_utilization_usd": round(weekly_target_usd, 4),
                "actual_gap_to_target_usd": round(weekly_gap_to_target_actual, 4),
                "forecast_gap_to_target_usd": round(weekly_gap_to_target_forecast, 4),
                "optimization_state": weekly_optimization_state,
                "suggested_additional_spend_to_target_usd": round(weekly_gap_to_target_forecast, 4),
                "days_remaining_in_week_fractional": round(days_remaining_week, 3),
                "days_remaining_in_week_calendar": days_remaining_calendar,
                "daily_spend_needed_to_hit_target_usd": round(daily_needed_to_hit_target, 4),
                "target_policy": {
                    "target_default_pct": optimization_policy["target_default_pct"],
                    "target_min_pct": optimization_policy["target_min_pct"],
                    "target_max_pct": optimization_policy["target_max_pct"],
                    "reasons": target_reasons,
                },
                # Backward-compat aliases for existing consumers.
                "target_90_pct_usd": round(weekly_target_usd, 4),
                "actual_gap_to_90_pct_target_usd": round(weekly_gap_to_target_actual, 4),
                "forecast_gap_to_90_pct_target_usd": round(weekly_gap_to_target_forecast, 4),
                "suggested_additional_spend_to_90_pct_usd": round(weekly_gap_to_target_forecast, 4),
                "daily_spend_needed_to_hit_90_pct_usd": round(daily_needed_to_hit_target, 4),
            },
            "monthly": {
                "cap_usd": monthly_cap,
                "current_usd": round(monthly_spent, 4),
                "remaining_usd": round(max(0.0, monthly_cap - monthly_spent), 4),
            },
        },
        "forecast": {
            "end_of_day_usd": round(day_projection, 4),
            "end_of_week_usd": round(week_projection, 4),
            "end_of_month_usd": round(month_projection, 4),
            "daily_over_cap": day_projection > daily_cap,
            "weekly_over_cap": week_projection > weekly_cap,
            "monthly_over_cap": month_projection > monthly_cap,
            "daily_utilization_forecast": round(day_ratio, 4),
            "weekly_utilization_forecast": round(week_ratio, 4),
            "monthly_utilization_forecast": round(month_ratio, 4),
            "risk_level": risk_level,
        },
        "model_usage": {
            "top_provider": provider_top,
            "top_model": model_top,
            "provider_burn_breakdown": provider_breakdown,
            "provider_burn_breakdown_basis": "estimated_by_event_share",
            "unknown_usage": unknown_usage,
        },
        "channels": channels,
    }


def _statusline_line(snapshot: dict[str, Any]) -> str:
    boot = snapshot.get("boot") or {}
    burn = snapshot.get("burn") or {}
    forecast = snapshot.get("forecast") or {}
    limits = snapshot.get("limits") or {}
    weekly = limits.get("weekly") if isinstance(limits.get("weekly"), dict) else {}
    model_usage = snapshot.get("model_usage") or {}
    unknown_usage = model_usage.get("unknown_usage") if isinstance(model_usage.get("unknown_usage"), dict) else {}
    provider = (model_usage.get("top_provider") or {}).get("name", "unknown")
    model = (model_usage.get("top_model") or {}).get("name", "unknown")
    trend = float(burn.get("weekly_trend_pct", 0.0) or 0.0)
    trend_sign = "+" if trend > 0 else ""
    risk = str(forecast.get("risk_level", "green") or "green").lower()
    risk_glyph = {"green": "G", "yellow": "Y", "red": "R"}.get(risk, "?")
    weekly_remaining_actual = float(weekly.get("remaining_usd", 0.0) or 0.0)
    weekly_remaining_forecast = float(weekly.get("forecast_remaining_usd", 0.0) or 0.0)
    weekly_gap_to_target = float(
        weekly.get("forecast_gap_to_target_usd", weekly.get("forecast_gap_to_90_pct_target_usd", 0.0)) or 0.0
    )
    weekly_target_pct = float(weekly.get("target_utilization_pct", 90.0) or 90.0)
    unknown_warn = bool(unknown_usage.get("warning", False))
    unknown_share = float(unknown_usage.get("unknown_share", 0.0) or 0.0)
    unknown_tag = f" unknown:{unknown_share:.0%}" if unknown_warn else ""
    return (
        f"[{risk_glyph}] "
        "boot "
        f"{int(boot.get('estimated_tokens', 0)):,}t | "
        "burn "
        f"${float(burn.get('daily_spent_usd', 0.0)):.2f}/d ${float(burn.get('weekly_spent_usd', 0.0)):.2f}/w | "
        "trend "
        f"{trend_sign}{trend:.1f}% | "
        "weekly "
        f"${float(weekly.get('current_usd', 0.0)):.2f}/${float(weekly.get('cap_usd', 0.0)):.2f} "
        f"remA:${weekly_remaining_actual:.2f} remF:${weekly_remaining_forecast:.2f} "
        f"gap{weekly_target_pct:.0f}:${weekly_gap_to_target:.2f} "
        f"need/day:${float(weekly.get('daily_spend_needed_to_hit_target_usd', weekly.get('daily_spend_needed_to_hit_90_pct_usd', 0.0))):.2f} | "
        "forecast "
        f"d:${float(forecast.get('end_of_day_usd', 0.0)):.2f} "
        f"w:${float(forecast.get('end_of_week_usd', 0.0)):.2f} "
        f"m:${float(forecast.get('end_of_month_usd', 0.0)):.2f} | "
        "model "
        f"{provider}/{model}{unknown_tag}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build budget forecast snapshot")
    parser.add_argument("--write", action="store_true", help="Write forecast artifact")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output artifact path")
    parser.add_argument(
        "--format",
        choices=["json", "line"],
        default="json",
        help="Output format to stdout",
    )
    args = parser.parse_args()

    snapshot = build_snapshot()
    if args.write:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        history_row = {
            "generated_at": snapshot.get("generated_at"),
            "forecast": snapshot.get("forecast") or {},
            "burn": snapshot.get("burn") or {},
            "channels": snapshot.get("channels") or {},
            "limits": {
                "weekly": ((snapshot.get("limits") or {}).get("weekly") or {}),
                "daily": ((snapshot.get("limits") or {}).get("daily") or {}),
                "monthly": ((snapshot.get("limits") or {}).get("monthly") or {}),
            },
        }
        with HISTORY_OUT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(history_row) + "\n")

    if args.format == "line":
        print(_statusline_line(snapshot))
    else:
        print(json.dumps(snapshot, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
