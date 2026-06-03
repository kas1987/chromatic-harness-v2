#!/usr/bin/env python3
"""Usage-calibration engine (harness side).

Back out Anthropic's hidden token caps from logged usage vs. native rate-limit
percentages, using the anchor-independent snapshot-delta method:

    cap = Δ(our weighted tokens, t1->t2)  /  ((pct_t2 - pct_t1) / 100)

for every consecutive snapshot pair inside the same window (no reset between
them). Estimates are aggregated by median. Writes calibrated_caps.json (harness
+ edge copy) and appends a calibration_history.jsonl entry.

Run after usage_ingest.py. Idempotent for a given input set.
"""
from __future__ import annotations
import bisect
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_calibration_lib as L

WINDOWS = ("five_hour", "seven_day")
WINDOW_SECONDS = {"five_hour": 5 * 3600, "seven_day": 7 * 86400}
MIN_DELTA_PCT = 0.5          # ignore pairs whose % barely moved (coarse/idle)
MIN_OK_ESTIMATES = 5         # below this => "provisional"
MAX_OK_SPREAD_PCT = 25       # relative spread above this => "provisional"


def _load_cumulative_timeline():
    """Return (sorted_ts, cumulative_wtok) plus per-model cumulative maps.

    cumulative_wtok[i] = total wtok of all events with ts <= sorted_ts[i].
    """
    events = [e for e in L.iter_jsonl(L.WTOK_EVENTS) if e.get("ts") is not None]
    events.sort(key=lambda e: e["ts"])
    ts_list, cum, cum_by_model = [], [], []
    running = 0.0
    running_models: dict[str, float] = {}
    for e in events:
        running += e.get("wtok", 0) or 0
        fam = L.model_type(e.get("model"))
        running_models[fam] = running_models.get(fam, 0.0) + (e.get("wtok", 0) or 0)
        ts_list.append(e["ts"])
        cum.append(running)
        cum_by_model.append(dict(running_models))
    return ts_list, cum, cum_by_model


def _cumulative_at(ts_list, cum, ts):
    """Total wtok accumulated at or before `ts` (0 if before all events)."""
    if not ts_list or ts is None:
        return 0.0
    i = bisect.bisect_right(ts_list, ts) - 1
    return cum[i] if i >= 0 else 0.0


def _is_reset(prev, cur):
    """True if a window reset happened between two snapshots of the same window."""
    if prev.get("pct") is None or cur.get("pct") is None:
        return True
    if cur["pct"] < prev["pct"] - 1e-9:       # utilization dropped => reset
        return True
    if prev.get("resets_at") != cur.get("resets_at"):  # window boundary moved
        return True
    return False


def _estimate_caps(window, snapshots, ts_list, cum):
    """Collect cap estimates for one window from consecutive same-window pairs."""
    pts = [(s["ts"], s.get(window)) for s in snapshots if s.get("ts") and s.get(window)]
    pts.sort(key=lambda p: p[0])
    estimates = []
    for (t1, w1), (t2, w2) in zip(pts, pts[1:]):
        if _is_reset(w1, w2):
            continue
        dpct = w2["pct"] - w1["pct"]
        if dpct < MIN_DELTA_PCT:
            continue
        dwtok = _cumulative_at(ts_list, cum, t2) - _cumulative_at(ts_list, cum, t1)
        if dwtok <= 0:
            continue
        cap = dwtok / (dpct / 100.0)
        if cap > 0 and cap != float("inf"):
            estimates.append(cap)
    return estimates


def _aggregate(estimates):
    if not estimates:
        return {"cap_wtok": None, "confidence": "none", "n_estimates": 0, "spread_pct": None}
    cap = statistics.median(estimates)
    n = len(estimates)
    if n >= 4:
        q = statistics.quantiles(estimates, n=4)  # [p25, p50, p75]
        spread = (q[2] - q[0]) / cap * 100 if cap else None
    else:
        spread = (max(estimates) - min(estimates)) / cap * 100 if cap else None
    if n >= MIN_OK_ESTIMATES and spread is not None and spread <= MAX_OK_SPREAD_PCT:
        conf = "ok"
    else:
        conf = "prov"
    return {"cap_wtok": round(cap), "confidence": conf,
            "n_estimates": n, "spread_pct": round(spread) if spread is not None else None}


def _current_window_usage(window, snapshots, ts_list, cum):
    """Weighted tokens used in the current window, from the latest snapshot's
    resets_at (window start = resets_at - duration). Returns (used_wtok, latest_pct)
    or (None, None) when unknown."""
    latest = None
    for s in snapshots:
        w = s.get(window)
        if w and w.get("resets_at"):
            if latest is None or s["ts"] > latest["ts"]:
                latest = s
    if not latest:
        return None, None
    w = latest[window]
    start = w["resets_at"] - WINDOW_SECONDS[window]
    used = _cumulative_at(ts_list, cum, latest["ts"]) - _cumulative_at(ts_list, cum, start)
    return max(0.0, used), w.get("pct")


def calibrate():
    _, version = L.load_weights()
    ts_list, cum, _ = _load_cumulative_timeline()
    snapshots = [s for s in L.iter_jsonl(L.SNAPSHOTS_ARCHIVE) if s.get("ts")]

    caps = {}
    for window in WINDOWS:
        agg = _aggregate(_estimate_caps(window, snapshots, ts_list, cum))
        used, pct = _current_window_usage(window, snapshots, ts_list, cum)
        agg["used_wtok"] = round(used) if used is not None else None
        agg["latest_pct"] = pct
        caps[window] = agg

    out = {
        "updated_at": L._now_iso(),
        "weight_table_version": version,
        "epoch_id": version,  # P2 replaces this with regime-aware epochs
        **caps,
    }
    L.write_json(L.CALIBRATED_CAPS, out)
    L.write_json(L.EDGE_CALIBRATED_CAPS, out)  # feedback copy the statusline reads
    L.append_jsonl(L.CALIBRATION_HISTORY, out)
    return out


def main():
    out = calibrate()
    for w in WINDOWS:
        c = out[w]
        print(f"{w}: cap={c['cap_wtok']} wtok  conf={c['confidence']}  "
              f"n={c['n_estimates']}  spread={c['spread_pct']}%")


if __name__ == "__main__":
    main()
