#!/usr/bin/env python3
"""Token/USD budget guard for long-running autonomous loops (OMH-3, w1bf.3).

Complements 02_RUNTIME/router/loop_guard.py (which guards *iteration count* — same task
fired N times) by guarding *cumulative spend*. A long /loop or /crank should pause when it
crosses a token or USD ceiling so a slow drip can't run the budget down unnoticed.

Reads the existing budget ledger (07_LOGS_AND_AUDIT/budget/ledger.jsonl) and sums spend,
optionally within a recent window. Verdict: ok | warn | pause.

  python scripts/loop_budget_guard.py --check                 # exit 0 ok, 3 pause
  python scripts/loop_budget_guard.py --max-usd 5 --json
  python scripts/loop_budget_guard.py --window-hours 24 --max-tokens 2000000
Fail-open: any IO/parse error → ok (a guard malfunction must never strand a loop).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO / "07_LOGS_AND_AUDIT" / "budget" / "ledger.jsonl"

# Generous defaults so --check passes unless a real ceiling is set (env or flag).
DEFAULT_MAX_USD = float(os.environ.get("LOOP_BUDGET_MAX_USD", "0") or 0)  # 0 = no USD ceiling
DEFAULT_MAX_TOKENS = int(os.environ.get("LOOP_BUDGET_MAX_TOKENS", "0") or 0)  # 0 = no token ceiling
WARN_FRACTION = 0.8


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def sum_spend(ledger: Path, window_hours: float | None = None) -> dict[str, Any]:
    """Sum tokens + usd from the ledger, optionally within the last window_hours."""
    total_tokens = 0
    total_usd = 0.0
    rows = 0
    if not ledger.exists():
        return {"tokens": 0, "usd": 0.0, "rows": 0}
    cutoff = _now() - timedelta(hours=window_hours) if window_hours else None
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate partial writes
        if cutoff is not None:
            ts = _parse_ts(rec.get("ts"))
            if ts is not None and ts < cutoff:
                continue
        total_tokens += int(rec.get("tokens") or 0)
        total_usd += float(rec.get("usd") or 0.0)
        rows += 1
    return {"tokens": total_tokens, "usd": round(total_usd, 4), "rows": rows}


def verdict(spend: dict[str, Any], max_usd: float, max_tokens: int) -> dict[str, Any]:
    level = "ok"
    reasons = []
    for name, used, limit in (("usd", spend["usd"], max_usd), ("tokens", spend["tokens"], max_tokens)):
        if limit and used >= limit:
            level = "pause"
            reasons.append(f"{name} {used} >= ceiling {limit}")
        elif limit and used >= limit * WARN_FRACTION and level != "pause":
            level = "warn"
            reasons.append(f"{name} {used} >= {int(WARN_FRACTION * 100)}% of {limit}")
    return {"level": level, "reasons": reasons, "spend": spend, "limits": {"usd": max_usd, "tokens": max_tokens}}


def main() -> int:
    p = argparse.ArgumentParser(description="Pause a long autonomous loop when spend crosses a ceiling.")
    p.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    p.add_argument("--max-usd", type=float, default=DEFAULT_MAX_USD)
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--window-hours", type=float, default=None, help="Only sum spend within the last N hours")
    p.add_argument("--check", action="store_true", help="Exit 3 if the loop should pause, else 0")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        spend = sum_spend(Path(args.ledger), args.window_hours)
        v = verdict(spend, args.max_usd, args.max_tokens)
    except Exception as exc:  # fail-open
        v = {"level": "ok", "reasons": [f"guard error (fail-open): {exc}"], "spend": {}, "limits": {}}

    if args.json:
        print(json.dumps(v))
    else:
        msg = f"loop-budget: {v['level'].upper()} | usd={v['spend'].get('usd')} tokens={v['spend'].get('tokens')}"
        if v["reasons"]:
            msg += " | " + "; ".join(v["reasons"])
        print(msg)

    if args.check and v["level"] == "pause":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
