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
import argparse
import bisect
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_calibration_lib as L

WINDOWS = ("five_hour", "seven_day")
WINDOW_SECONDS = {"five_hour": 5 * 3600, "seven_day": 7 * 86400}
MIN_DELTA_PCT = 0.5  # ignore pairs whose % barely moved (coarse/idle)
MIN_OK_ESTIMATES = 5  # below this => "provisional"
MAX_OK_SPREAD_PCT = 25  # relative spread above this => "provisional"
REGIME_THRESHOLD_PCT = 40  # firm-cap shift beyond this is a regime-change candidate
REGIME_CONFIRM = 3  # consecutive candidate runs before opening a new epoch


def _load_cumulative_timeline(weights=None):
    """Return (sorted_ts, cumulative_wtok, cum_by_model).

    cumulative_wtok[i] = total wtok of all events with ts <= sorted_ts[i]. When
    `weights` is given, wtok is recomputed from each event's raw usage (used by
    `recalibrate --weights` to re-derive caps under an alternate weight table);
    otherwise the stored per-event wtok is used.
    """
    events = [e for e in L.iter_jsonl(L.WTOK_EVENTS) if e.get("ts") is not None]
    events.sort(key=lambda e: e["ts"])
    ts_list, cum, cum_by_model = [], [], []
    running = 0.0
    running_models: dict[str, float] = {}
    for e in events:
        if weights is not None and isinstance(e.get("raw"), dict):
            w = L.wtok(e["raw"], e.get("model"), weights)
        else:
            w = e.get("wtok", 0) or 0
        running += w
        fam = L.model_type(e.get("model"))
        running_models[fam] = running_models.get(fam, 0.0) + w
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
    if cur["pct"] < prev["pct"] - 1e-9:  # utilization dropped => reset
        return True
    if prev.get("resets_at") != cur.get("resets_at"):  # window boundary moved
        return True
    return False


def _estimate_caps(window, snapshots, ts_list, cum):
    """Collect cap estimates for one window from consecutive same-window pairs."""
    pts = [(s["ts"], s.get(window)) for s in snapshots if s.get("ts") is not None and s.get(window)]
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
    return {
        "cap_wtok": round(cap),
        "confidence": conf,
        "n_estimates": n,
        "spread_pct": round(spread) if spread is not None else None,
    }


def _current_window_usage(window, snapshots, ts_list, cum):
    """Weighted tokens used in the current window, from the latest snapshot's
    resets_at (window start = resets_at - duration). Returns
    (used_wtok, latest_pct, latest_snapshot) or (None, None, None) when unknown."""
    latest = None
    for s in snapshots:
        w = s.get(window)
        if w and w.get("resets_at"):
            if latest is None or s["ts"] > latest["ts"]:
                latest = s
    if not latest:
        return None, None, None
    w = latest[window]
    start = w["resets_at"] - WINDOW_SECONDS[window]
    used = _cumulative_at(ts_list, cum, latest["ts"]) - _cumulative_at(ts_list, cum, start)
    return max(0.0, used), w.get("pct"), latest


def _forecast(window, latest, used_wtok, cap_wtok):
    """Burn rate + time-to-cap for a window. None if not computable.

    burn = used so far / hours elapsed in the window; time_to_cap = remaining /
    burn; verdict compares that to the time left until the window resets.
    """
    w = latest.get(window) or {}
    resets_at = w.get("resets_at")
    if not resets_at or cap_wtok is None or used_wtok is None:
        return None
    start = resets_at - WINDOW_SECONDS[window]
    elapsed_hr = (latest["ts"] - start) / 3600.0
    hours_to_reset = max(0.0, (resets_at - latest["ts"]) / 3600.0)
    if elapsed_hr <= 0:
        return None
    burn = used_wtok / elapsed_hr  # wtok / hr
    remaining = max(0.0, cap_wtok - used_wtok)
    time_to_cap_hr = remaining / burn if burn > 0 else None
    verdict = "ok"
    if time_to_cap_hr is not None and time_to_cap_hr < hours_to_reset:
        verdict = "cap_before_reset"
    return {
        "burn_wtok_per_hr": round(burn),
        "time_to_cap_hr": round(time_to_cap_hr, 2) if time_to_cap_hr is not None else None,
        "hours_to_reset": round(hours_to_reset, 2),
        "safe_burn_wtok_per_hr": round(remaining / hours_to_reset) if hours_to_reset > 0 else None,
        "verdict": verdict,
    }


def _load_epochs():
    """Return the epochs registry, initializing epoch e1 (from time 0) if absent."""
    data = L.read_json(L.EPOCHS)
    if not data or not data.get("epochs"):
        data = {
            "epochs": [{"id": "e1", "start_ts": 0, "reason": "init", "opened_at": L._now_iso()}],
            "current": "e1",
            "regime_streak": 0,
        }
    return data


def _current_epoch(epochs):
    cur = epochs.get("current")
    for e in epochs["epochs"]:
        if e["id"] == cur:
            return e
    return epochs["epochs"][-1]


def _epoch_baseline(epoch_id, window):
    """Median firm (ok) cap recorded for this epoch+window in history, or None."""
    vals = []
    for h in L.iter_jsonl(L.CALIBRATION_HISTORY):
        if h.get("epoch_id") != epoch_id:
            continue
        w = h.get(window) or {}
        if w.get("confidence") == "ok" and w.get("cap_wtok"):
            vals.append(w["cap_wtok"])
    return statistics.median(vals) if vals else None


def _compute_caps(epoch_start, snapshots, ts_list, cum):
    """Caps for every window using only snapshots within [epoch_start, ∞)."""
    scoped = [s for s in snapshots if s["ts"] >= epoch_start]
    caps = {}
    for window in WINDOWS:
        agg = _aggregate(_estimate_caps(window, scoped, ts_list, cum))
        used, pct, latest = _current_window_usage(window, scoped, ts_list, cum)
        agg["used_wtok"] = round(used) if used is not None else None
        agg["latest_pct"] = pct
        # Forecast only meaningful once the cap is firm.
        if agg["confidence"] == "ok" and agg["cap_wtok"] and latest:
            agg["forecast"] = _forecast(window, latest, used, agg["cap_wtok"])
        else:
            agg["forecast"] = None
        caps[window] = agg
    return caps


def _detect_regime(epochs, epoch, caps, latest_ts=0):
    """Update regime streak; open a new epoch on a sustained firm-cap shift.

    Returns (epochs, epoch, regime_event_or_None). A regime is flagged when a
    window whose cap is 'ok' deviates from its established epoch baseline by more
    than REGIME_THRESHOLD_PCT for REGIME_CONFIRM consecutive runs — then we
    re-baseline into a fresh epoch rather than blend pre/post-change data.

    latest_ts is passed explicitly (rather than stored on the epoch dict) to
    avoid mutating epoch with temporary state that could leak into epochs.json.
    """
    signal = None
    for window in WINDOWS:  # prefer five_hour (moves faster), fall back to weekly
        c = caps[window]
        if c["confidence"] == "ok" and c["cap_wtok"]:
            base = _epoch_baseline(epoch["id"], window)
            if base:
                dev = abs(c["cap_wtok"] - base) / base * 100
                signal = (window, c["cap_wtok"], base, dev)
                break
    if not signal or signal[3] <= REGIME_THRESHOLD_PCT:
        epochs["regime_streak"] = 0
        return epochs, epoch, None

    epochs["regime_streak"] = epochs.get("regime_streak", 0) + 1
    if epochs["regime_streak"] < REGIME_CONFIRM:
        return epochs, epoch, None

    # Sustained shift confirmed → open a new epoch starting now.
    window, new_cap, base, dev = signal
    new_id = f"e{len(epochs['epochs']) + 1}"
    reason = f"{window} cap {round(base)}→{round(new_cap)} wtok ({round(dev)}% shift)"
    new_epoch = {"id": new_id, "start_ts": latest_ts, "reason": reason, "opened_at": L._now_iso()}
    epochs["epochs"].append(new_epoch)
    epochs["current"] = new_id
    epochs["regime_streak"] = 0
    return epochs, new_epoch, reason


def calibrate(from_ts=None, weights_path=None, write=True):
    """Run a calibration pass.

    Normal mode (from_ts=None): epoch-aware — scope estimates to the current
    epoch, detect regime shifts, persist caps + history + epochs.
    Recompute mode (from_ts set): scope estimates to [from_ts, ∞), do NOT mutate
    epochs/history; return the caps (persist only when write=True).
    weights_path overrides the weight table for the wtok timeline.
    """
    # Load the weight table to get an accurate version tag regardless of path.
    # When weights_path is given, also recompute per-event wtok from raw usage so
    # weight_table_version and the cap estimates are consistent.
    # In normal mode (no weights_path), stored per-event wtok is used for performance;
    # version reflects the current committed table (the same one used at ingest time
    # unless the table was manually changed between ingest and calibration).
    if weights_path:
        weights, version = L.load_weights(weights_path)
    else:
        weights, version = None, L.load_weights()[1]
    ts_list, cum, _ = _load_cumulative_timeline(weights=weights)
    snapshots = [s for s in L.iter_jsonl(L.SNAPSHOTS_ARCHIVE) if s.get("ts") is not None]
    latest_ts = max((s["ts"] for s in snapshots), default=0)

    if from_ts is not None:
        caps = _compute_caps(from_ts, snapshots, ts_list, cum)
        out = {
            "updated_at": L._now_iso(),
            "weight_table_version": version,
            "epoch_id": "recompute",
            "from_ts": from_ts,
            **caps,
        }
        if write:
            L.write_json(L.CALIBRATED_CAPS, out)
            L.write_json(L.EDGE_CALIBRATED_CAPS, out)
        return out

    epochs = _load_epochs()
    epoch = _current_epoch(epochs)
    caps = _compute_caps(epoch["start_ts"], snapshots, ts_list, cum)
    epochs, epoch, regime = _detect_regime(epochs, epoch, caps, latest_ts)
    if regime:  # re-baseline: recompute within the freshly opened epoch
        caps = _compute_caps(epoch["start_ts"], snapshots, ts_list, cum)

    out = {
        "updated_at": L._now_iso(),
        "weight_table_version": version,
        "epoch_id": epoch["id"],
        "regime_change": regime,
        **caps,
    }
    if write:
        L.write_json(L.CALIBRATED_CAPS, out)
        L.write_json(L.EDGE_CALIBRATED_CAPS, out)  # feedback copy the statusline reads
        L.append_jsonl(L.CALIBRATION_HISTORY, out)
        L.write_json(L.EPOCHS, epochs)
    return out


def _parse_from(value):
    """Parse --from as an ISO date/datetime or epoch seconds → epoch int."""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        from datetime import datetime

        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def main(argv=None):
    ap = argparse.ArgumentParser(description="Calibrate Anthropic token caps from logged usage.")
    ap.add_argument(
        "--from",
        dest="from_ts",
        metavar="DATE|EPOCH",
        help="Recompute over [DATE, now] only; does not mutate epochs/history.",
    )
    ap.add_argument("--weights", metavar="PATH", help="Alternate weight_table.json to recompute wtok under.")
    ap.add_argument("--reset-epochs", action="store_true", help="Delete the epoch registry and start a fresh epoch e1.")
    ap.add_argument("--dry-run", action="store_true", help="Compute and print but do not persist.")
    args = ap.parse_args(argv)

    if args.reset_epochs:
        try:
            L.EPOCHS.unlink()
        except (FileNotFoundError, OSError):
            pass
        print("epochs reset")

    out = calibrate(from_ts=_parse_from(args.from_ts), weights_path=args.weights, write=not args.dry_run)
    if out.get("regime_change"):
        print(f"REGIME CHANGE → new epoch {out['epoch_id']}: {out['regime_change']}")
    for w in WINDOWS:
        c = out[w]
        print(
            f"{w}: cap={c['cap_wtok']} wtok  conf={c['confidence']}  "
            f"n={c['n_estimates']}  spread={c['spread_pct']}%  "
            f"[epoch {out['epoch_id']}]"
        )


if __name__ == "__main__":
    main()
