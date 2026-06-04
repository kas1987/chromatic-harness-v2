#!/usr/bin/env python3
"""Usage rollup (harness side): session -> daily -> weekly -> monthly.

Buckets the weighted-token event stream into the windows the user reasons in:
per-session, per-day, per-week (Tuesday 1pm ET -> next Tuesday 1pm ET), and
per-month. Weekly uses the same fixed anchor as Anthropic's observed reset.
Writes rollup.json (latest buckets + recent history). Run after usage_ingest.py.
Idempotent: derived purely from wtok_events.jsonl.
"""
from __future__ import annotations
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_calibration_lib as L


def _accumulate():
    """Sum wtok + event counts per bucket across each time grain."""
    grains = {
        "session": defaultdict(lambda: {"wtok": 0.0, "events": 0}),
        "daily": defaultdict(lambda: {"wtok": 0.0, "events": 0}),
        "weekly": defaultdict(lambda: {"wtok": 0.0, "events": 0}),
        "monthly": defaultdict(lambda: {"wtok": 0.0, "events": 0}),
        # per-model weekly split feeds the "all-models vs sonnet-only" tracks.
        "weekly_by_model": defaultdict(lambda: defaultdict(float)),
    }
    for e in L.iter_jsonl(L.WTOK_EVENTS):
        ts, w = e.get("ts"), (e.get("wtok") or 0)
        if ts is None:
            continue
        keys = {
            "session": e.get("session_id") or "unknown",
            "daily": L.day_key(ts),
            "weekly": L.week_start_key(ts),
            "monthly": L.month_key(ts),
        }
        for grain, key in keys.items():
            grains[grain][key]["wtok"] += w
            grains[grain][key]["events"] += 1
        grains["weekly_by_model"][L.week_start_key(ts)][L.model_type(e.get("model"))] += w
    return grains


def _round_bucket(b):
    return {"wtok": round(b["wtok"]), "events": b["events"]}


def build_rollup():
    g = _accumulate()
    caps = L.read_json(L.CALIBRATED_CAPS)

    def _with_cap_pct(buckets, cap_key):
        cap = (caps.get(cap_key) or {}).get("cap_wtok") if isinstance(caps, dict) else None
        ok = isinstance(caps, dict) and (caps.get(cap_key) or {}).get("confidence") == "ok"
        out = {}
        for k, b in sorted(buckets.items()):
            rec = _round_bucket(b)
            if cap and ok:
                rec["pct_of_cap"] = round(b["wtok"] / cap * 100, 1)
            out[k] = rec
        return out

    rollup = {
        "updated_at": L._now_iso(),
        "weekly": _with_cap_pct(g["weekly"], "seven_day"),
        "daily": {k: _round_bucket(b) for k, b in sorted(g["daily"].items())},
        "monthly": {k: _round_bucket(b) for k, b in sorted(g["monthly"].items())},
        "sessions": {k: _round_bucket(b) for k, b in sorted(g["session"].items())},
        "weekly_by_model": {
            wk: {m: round(v) for m, v in sorted(models.items())}
            for wk, models in sorted(g["weekly_by_model"].items())
        },
    }
    return rollup


def main():
    rollup = build_rollup()
    L.write_json(L.ROLLUP, rollup)
    wk = rollup["weekly"]
    cur = list(wk.items())[-1] if wk else None
    n = sum(b["events"] for b in rollup["daily"].values())
    print(f"rollup: {len(rollup['daily'])} day(s), {len(wk)} week(s), {n} events"
          + (f"; current week {cur[0]} = {cur[1]['wtok']} wtok" if cur else ""))


if __name__ == "__main__":
    main()
