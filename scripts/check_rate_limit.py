"""Live budget status check + dashboard links.

WHAT IS LIVE (computed fresh each run):
  - Claude Code USD spend via budget_forecast_snapshot.py -> daily.jsonl

WHAT IS DASHBOARD-ONLY (no API exists for either):
  - Claude plan limits (5-hour, weekly, Sonnet)  -> claude.ai  (Settings > Usage)
  - Ollama Pro cloud call quotas                 -> ollama.com/settings/usage

The plan-limit snapshots in ollama-forecast.jsonl are manually written and stale
after any 5-hour window resets. Do not treat them as live.

Exits 0 if USD thresholds OK, 1 if exceeded.
Run: python scripts/check_rate_limit.py [--json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FORECAST_SCRIPT = REPO / "scripts" / "budget_forecast_snapshot.py"
QUOTA_STATE = Path.home() / ".claude" / "powerline" / "usage" / "quota_state.json"
STALE_HOURS = 6  # warn if quota_state.json is older than this

# USD thresholds (from budget caps in agent_budget.yaml or defaults)
WEEKLY_WARN_PCT = 75.0
WEEKLY_CRITICAL_PCT = 90.0
DAILY_WARN_PCT = 80.0


def _load_quota_state() -> dict | None:
    """Load Claude plan limits from quota_state.json (written by quota-capture.py)."""
    if not QUOTA_STATE.exists():
        return None
    try:
        return json.loads(QUOTA_STATE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run_live_snapshot() -> dict | None:
    """Run budget_forecast_snapshot.py and return parsed JSON."""
    try:
        result = subprocess.run(
            [PYTHON, str(FORECAST_SCRIPT), "--format", "json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception:
        return None



def _status_tag(pct: float, warn: float, crit: float) -> str:
    if pct >= crit:
        return "CRIT"
    if pct >= warn:
        return "WARN"
    return "OK"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    exit_code = 0
    output: dict = {}

    # ── 1. Live Claude Code USD spend ────────────────────────────────────────
    snap = _run_live_snapshot()
    if snap:
        burn = snap.get("burn", {})
        limits = snap.get("limits", {})
        forecast = snap.get("forecast", {})
        weekly = limits.get("weekly", {})
        daily = limits.get("daily", {})

        weekly_spent = float(burn.get("weekly_spent_usd", 0))
        weekly_cap = float(weekly.get("cap_usd", 100))
        weekly_pct = (weekly_spent / weekly_cap * 100) if weekly_cap else 0

        daily_spent = float(burn.get("daily_spent_usd", 0))
        daily_cap = float(daily.get("cap_usd", 25))
        daily_pct = (daily_spent / daily_cap * 100) if daily_cap else 0

        weekly_tag = _status_tag(weekly_pct, WEEKLY_WARN_PCT, WEEKLY_CRITICAL_PCT)
        daily_tag = _status_tag(daily_pct, DAILY_WARN_PCT, 95.0)
        risk = str(forecast.get("risk_level", "green")).upper()

        if weekly_tag != "OK" or daily_tag != "OK":
            exit_code = 1

        output["claude_code_usd"] = {
            "status": weekly_tag if weekly_tag != "OK" else daily_tag,
            "risk_level": risk,
            "daily": {"spent": round(daily_spent, 4), "cap": daily_cap, "pct": round(daily_pct, 1)},
            "weekly": {"spent": round(weekly_spent, 4), "cap": weekly_cap, "pct": round(weekly_pct, 1)},
            "burn_rate_daily_usd": round(float(burn.get("daily_burn_rate_usd", 0)), 4),
            "weekly_trend_pct": float(burn.get("weekly_trend_pct", 0)),
            "eow_forecast_usd": round(float(forecast.get("end_of_week_usd", 0)), 4),
        }

        if not args.json:
            tag = output["claude_code_usd"]["status"]
            print(f"[claude-code] {tag}  risk={risk}")
            print(f"  Daily  : ${daily_spent:.2f} / ${daily_cap:.0f}  ({daily_pct:.1f}%)")
            print(f"  Weekly : ${weekly_spent:.2f} / ${weekly_cap:.0f}  ({weekly_pct:.1f}%)")
            print(f"  Burn   : ${burn.get('daily_burn_rate_usd', 0):.2f}/day  "
                  f"trend {burn.get('weekly_trend_pct', 0):+.1f}%  "
                  f"EoW forecast ${forecast.get('end_of_week_usd', 0):.2f}")
    else:
        output["claude_code_usd"] = {"status": "UNAVAILABLE", "error": "budget_forecast_snapshot.py failed"}
        if not args.json:
            print("[claude-code] UNAVAILABLE - could not run budget_forecast_snapshot.py")

    # ── 3. Claude plan limits from quota_state.json (fed by Chrome scrape routine) ──
    quota_data = _load_quota_state()
    if quota_data:
        from datetime import datetime, timezone, timedelta
        captured_at = quota_data.get("captured_at", "")
        source = quota_data.get("source", "unknown")
        weekly_pct = quota_data.get("weekly_pct")
        sonnet_pct = quota_data.get("weekly_sonnet_pct")
        session_pct = quota_data.get("session_5h_pct")
        weekly_reset = quota_data.get("weekly_reset", "")
        session_reset = quota_data.get("session_5h_reset", "")

        # Staleness check
        stale = False
        stale_msg = ""
        try:
            cap_dt = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - cap_dt).total_seconds() / 3600
            if age_h > STALE_HOURS:
                stale = True
                stale_msg = f" [STALE: {age_h:.1f}h old — run quota-capture.py to refresh]"
        except Exception:
            stale = True
            stale_msg = " [STALE: could not parse captured_at]"

        output["claude_plan"] = {
            "source": source,
            "captured_at": captured_at,
            "stale": stale,
            "weekly_all_models_pct": weekly_pct,
            "weekly_sonnet_pct": sonnet_pct,
            "session_5h_pct": session_pct,
            "weekly_reset": weekly_reset,
            "session_5h_reset": session_reset,
        }
        if not args.json:
            print()
            label = f"[claude-plan] source={source}{stale_msg}"
            print(label)
            print(f"  5h session  : {session_pct if session_pct is not None else '?'}%"
                  + (f"  resets {session_reset[:16]}" if session_reset else ""))
            print(f"  Weekly all  : {weekly_pct if weekly_pct is not None else '?'}%"
                  + (f"  resets {weekly_reset[:16]}" if weekly_reset else ""))
            print(f"  Weekly Sonnet: {sonnet_pct if sonnet_pct is not None else '?'}%")
            if stale:
                print("  To refresh: cd ~/.claude/bin && python quota-capture.py --pct <weekly> ...")
    else:
        output["claude_plan"] = {"note": "quota_state.json not found"}
        if not args.json:
            print()
            print("[claude-plan] No quota_state.json found")
            print("  Seed it: cd ~/.claude/bin && python quota-capture.py --pct 15 --session-pct 1 --sonnet-pct 13 --reset-days 5")

    # ── 4. Ollama Pro (no API — dashboard only) ───────────────────────────────
    if not args.json:
        print()
        print("[ollama-pro]  No API - check ollama.com/settings/usage  (email alerts enabled)")

    output["ollama_pro"] = {"note": "No API - dashboard only", "url": "ollama.com/settings/usage"}

    if args.json:
        print(json.dumps(output, indent=2))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
