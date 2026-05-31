#!/usr/bin/env python3
"""
Chromatic Harness KPI Console
Plain-Python ASCII report — no curses, no external deps.
Usage: python scripts/harness_kpi_console.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── helpers ──────────────────────────────────────────────────────────────────


def load_json(rel_path):
    p = ROOT / rel_path
    try:
        with open(p, encoding="utf-8") as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return None
    except Exception as e:
        return {"_load_error": str(e)}


def fmt_usd(val):
    if val is None:
        return "N/A"
    return f"${val:,.2f}"


def fmt_pct(val):
    if val is None:
        return "N/A"
    return f"{val:.1f}%"


def na(v, *, suffix=""):
    return "N/A" if v is None else f"{v}{suffix}"


def row(label, value, target="", width=45):
    label_part = f"  {label}"
    dots = "." * max(1, width - len(label_part) - len(str(value)))
    t = f"  {target}" if target else ""
    return f"{label_part} {dots} {value}{t}"


# ── load sinks ────────────────────────────────────────────────────────────────

health = load_json("07_LOGS_AND_AUDIT/harness_health/latest.json")
tok_gov = load_json("07_LOGS_AND_AUDIT/token_governance/latest.json")
guard = load_json("07_LOGS_AND_AUDIT/unified_guard/latest.json")
forecast = load_json("07_LOGS_AND_AUDIT/budget/forecast_latest.json")
learning = load_json("07_LOGS_AND_AUDIT/learning_tiers/latest.json")

# telemetry session count
tel_path = ROOT / "05_REPORTS" / "telemetry.jsonl"
session_count = 0
last_session_date = "N/A"
try:
    lines = [
        l.strip()
        for l in tel_path.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    session_count = len(lines)
    if lines:
        last_entry = json.loads(lines[-1])
        last_session_date = last_entry.get("date", "N/A")
except Exception:
    pass

# ── extract KPIs ──────────────────────────────────────────────────────────────

# GOVERNANCE ──────────────────────────────────────────────────────────────────
gov_pass = gov_warn = gov_fail = None
gov_readiness = None
gov_broken = None
if health and "_load_error" not in health:
    c = health.get("counts", {})
    gov_pass = c.get("pass")
    gov_warn = c.get("warn")
    gov_fail = c.get("fail")
    gov_readiness = health.get("readiness_score")
    # broken governance = fail count
    gov_broken = gov_fail

# Actions logged from unified_guard
actions_logged = None
if guard and "_load_error" not in guard:
    steps = guard.get("steps", [])
    actions_logged = len([s for s in steps if s.get("ok")])

# TOKEN / COST ─────────────────────────────────────────────────────────────────
weekly_burn = None
monthly_forecast = None
weekly_cap = None
axis_p_pct = None
unknown_pct = None

if forecast and "_load_error" not in forecast:
    burn = forecast.get("burn", {})
    weekly_burn = burn.get("weekly_spent_usd")
    fcast = forecast.get("forecast", {})
    monthly_forecast = fcast.get("end_of_month_usd")
    limits = forecast.get("limits", {})
    weekly_cap = limits.get("weekly", {}).get("cap_usd", 100.0)
    ap = forecast.get("axis_prepaid", {})
    axis_p_pct = ap.get("weekly_quota_pct")
    unk = forecast.get("model_usage", {}).get("unknown_usage", {})
    unknown_pct = unk.get("unknown_share")
    if unknown_pct is not None:
        unknown_pct = round(unknown_pct * 100, 1)

# LEARNING ────────────────────────────────────────────────────────────────────
total_learnings = None
applied_learnings = None
learn_app_rate = None
if learning and "_load_error" not in learning:
    total_learnings = learning.get("total_learnings")
    usage_events = learning.get("usage_events_total", 0)
    # E1+ = promoted/applied; E0 = baseline only
    pyramid = learning.get("pyramid", {})
    applied = sum(sum(v.values()) for k, v in pyramid.items() if k != "E0")
    applied_learnings = applied
    if total_learnings and total_learnings > 0:
        learn_app_rate = (
            f"{applied}/{total_learnings} ({applied / total_learnings * 100:.0f}%)"
        )
    else:
        learn_app_rate = "0/0"

# ── render ────────────────────────────────────────────────────────────────────

W = 55
DIV = "=" * W
DIV2 = "-" * W

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

print()
print(DIV)
print(f" CHROMATIC HARNESS — KPI CONSOLE")
print(f" {today}")
print(DIV)

# GOVERNANCE
print()
print(" GOVERNANCE")

readiness_str = f"{gov_readiness}/100" if gov_readiness is not None else "N/A"
print(row("Readiness score", readiness_str, "target 100"))

checks_str = (
    f"pass={gov_pass} warn={gov_warn} fail={gov_fail}"
    if gov_pass is not None
    else "N/A"
)
print(row("Health checks", checks_str))

print(row("Actions logged (guard steps)", na(actions_logged), "target 90%+"))
print(row("Broken governance files", na(gov_broken), "target 0"))

# TOKEN / COST
print()
print(" TOKEN / COST")

print(row("Cache-hit rate", "N/A", "(not yet tracked — see kpi_collectors/)"))
print(row("Router local-vs-cloud", "N/A", "(not yet tracked — see kpi_collectors/)"))

weekly_str = (
    f"{fmt_usd(weekly_burn)} / {fmt_usd(weekly_cap)}"
    if weekly_burn is not None
    else "N/A"
)
print(row("Weekly burn (actual/cap)", weekly_str))

monthly_str = fmt_usd(monthly_forecast)
print(row("Forecast end-of-month", monthly_str))

print(row("Axis-P prepaid quota used", fmt_pct(axis_p_pct), "target 90%"))
print(row("Unknown event share", fmt_pct(unknown_pct), "target <20%"))

# LEARNING
print()
print(" LEARNING")

print(row("Total learnings indexed", na(total_learnings)))
print(row("Applied (E1+) learnings", na(applied_learnings)))
print(row("Learning-application rate", na(learn_app_rate)))
print(row("Context-budget adherence", "N/A", "(not yet tracked — see kpi_collectors/)"))

# SESSIONS
print()
print(" SESSIONS")
print(row("Total logged (telemetry)", str(session_count)))
print(row("Last session date", last_session_date))

print()
print(DIV)
print(" Run kpi_collectors/ stubs to instrument missing KPIs.")
print(DIV)
print()
