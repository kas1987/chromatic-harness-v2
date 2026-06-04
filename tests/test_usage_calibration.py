"""Tests for the usage-calibration pipeline (weight math + snapshot-delta engine)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import usage_calibration_lib as L  # noqa: E402
import usage_calibrate as C  # noqa: E402
import usage_rollup as R  # noqa: E402
import datetime as _dt  # noqa: E402


def _epoch(y, mo, d, h=12):
    return int(_dt.datetime(y, mo, d, h, 0, tzinfo=_dt.timezone.utc).timestamp())


# ── Weight math & model normalization ───────────────────────────────────────--
def test_model_type_normalizes_suffixes():
    assert L.model_type("claude-opus-4-8[1m]") == "opus"
    assert L.model_type("claude-sonnet-4-6") == "sonnet"
    assert L.model_type("claude-haiku-4-5-20251001") == "haiku"
    assert L.model_type("some-unknown-model") == "default"
    assert L.model_type(None) == "default"


def test_wtok_weights_by_model_and_type():
    weights, _ = L.load_weights()
    # Opus: 100k input * 5 + 10k output * 25 = 500000 + 250000 = 750000
    assert L.wtok({"input_tokens": 100000, "output_tokens": 10000}, "claude-opus-4-8[1m]", weights) == 750000.0
    # Sonnet input is the reference unit (weight 1.0)
    assert L.wtok({"input_tokens": 100000}, "claude-sonnet-4-6", weights) == 100000.0
    # Accepts already-mapped keys too
    assert L.wtok({"input": 1000}, "claude-sonnet-4-6", weights) == 1000.0


# ── Snapshot-delta cap estimation ────────────────────────────────────────────
def _timeline():
    # cumulative wtok: 1000 @100, 2000 @200, 3000 @300, 4000 @400
    return [100, 200, 300, 400], [1000.0, 2000.0, 3000.0, 4000.0]


def test_estimate_caps_basic():
    ts_list, cum = _timeline()
    snaps = [
        {"ts": 100, "five_hour": {"pct": 5, "resets_at": 9999}},
        {"ts": 300, "five_hour": {"pct": 15, "resets_at": 9999}},
    ]
    # Δwtok = 3000-1000 = 2000; Δpct = 10 => cap = 2000 / 0.10 = 20000
    assert C._estimate_caps("five_hour", snaps, ts_list, cum) == [20000.0]


def test_estimate_caps_skips_reset():
    ts_list, cum = _timeline()
    snaps = [
        {"ts": 200, "five_hour": {"pct": 15, "resets_at": 9999}},
        {"ts": 400, "five_hour": {"pct": 2, "resets_at": 9999}},  # pct dropped => reset
    ]
    assert C._estimate_caps("five_hour", snaps, ts_list, cum) == []


def test_estimate_caps_skips_window_boundary_change():
    ts_list, cum = _timeline()
    snaps = [
        {"ts": 100, "five_hour": {"pct": 5, "resets_at": 1000}},
        {"ts": 300, "five_hour": {"pct": 15, "resets_at": 2000}},  # resets_at changed
    ]
    assert C._estimate_caps("five_hour", snaps, ts_list, cum) == []


def test_estimate_caps_skips_idle_below_min_delta():
    ts_list, cum = _timeline()
    snaps = [
        {"ts": 100, "five_hour": {"pct": 10.0, "resets_at": 9999}},
        {"ts": 300, "five_hour": {"pct": 10.2, "resets_at": 9999}},  # Δpct 0.2 < 0.5
    ]
    assert C._estimate_caps("five_hour", snaps, ts_list, cum) == []


# ── Aggregation & confidence ─────────────────────────────────────────────────
def test_aggregate_empty_is_none():
    r = C._aggregate([])
    assert r["cap_wtok"] is None and r["confidence"] == "none" and r["n_estimates"] == 0


def test_aggregate_single_is_provisional():
    r = C._aggregate([20000.0])
    assert r["cap_wtok"] == 20000 and r["confidence"] == "prov" and r["n_estimates"] == 1


def test_aggregate_tight_cluster_is_ok():
    r = C._aggregate([100000, 101000, 99000, 100500, 99500, 100200])
    assert r["confidence"] == "ok"
    assert abs(r["cap_wtok"] - 100000) < 2000


def test_aggregate_wide_spread_is_provisional():
    r = C._aggregate([50000, 100000, 200000, 80000, 300000, 60000])
    assert r["confidence"] == "prov"  # spread too wide despite n>=5


# ── End-to-end calibrate() + idempotency ─────────────────────────────────────
def test_calibrate_end_to_end(tmp_path, monkeypatch):
    wtok = tmp_path / "wtok_events.jsonl"
    arc = tmp_path / "snapshots_archive.jsonl"
    caps = tmp_path / "calibrated_caps.json"
    edge = tmp_path / "edge_caps.json"
    hist = tmp_path / "calibration_history.jsonl"
    monkeypatch.setattr(L, "WTOK_EVENTS", wtok)
    monkeypatch.setattr(L, "SNAPSHOTS_ARCHIVE", arc)
    monkeypatch.setattr(L, "CALIBRATED_CAPS", caps)
    monkeypatch.setattr(L, "EDGE_CALIBRATED_CAPS", edge)
    monkeypatch.setattr(L, "CALIBRATION_HISTORY", hist)
    monkeypatch.setattr(L, "EPOCHS", tmp_path / "epochs.json")

    # 5 evenly-spaced events of 1000 wtok each; 5h pct climbs 1%/event.
    for i, ts in enumerate([100, 200, 300, 400, 500, 600], start=1):
        L.append_jsonl(wtok, {"ts": ts, "model": "claude-sonnet-4-6", "request_id": f"r{i}", "raw": {}, "wtok": 1000})
    for i, ts in enumerate([100, 200, 300, 400, 500, 600]):
        L.append_jsonl(
            arc, {"ts": ts, "five_hour": {"pct": 5 + i, "resets_at": 9999}, "seven_day": {"pct": 16, "resets_at": 8888}}
        )

    out = C.calibrate()
    # Each step: Δwtok=1000, Δpct=1 => cap = 1000/0.01 = 100000
    assert out["five_hour"]["cap_wtok"] == 100000
    assert out["five_hour"]["confidence"] == "ok"
    assert out["seven_day"]["cap_wtok"] is None  # flat weekly => no estimate
    assert caps.exists() and edge.exists() and hist.exists()

    # Idempotent: same inputs => identical caps
    out2 = C.calibrate()
    assert out2["five_hour"]["cap_wtok"] == out["five_hour"]["cap_wtok"]
    assert out["epoch_id"] == "e1"  # fresh registry starts at epoch e1


# ── Epochs & regime detection (P2) ───────────────────────────────────────────
def _point_paths_to_tmp(tmp_path, monkeypatch):
    for attr, name in [
        ("WTOK_EVENTS", "wtok_events.jsonl"),
        ("SNAPSHOTS_ARCHIVE", "snapshots_archive.jsonl"),
        ("CALIBRATED_CAPS", "calibrated_caps.json"),
        ("EDGE_CALIBRATED_CAPS", "edge_caps.json"),
        ("CALIBRATION_HISTORY", "calibration_history.jsonl"),
        ("EPOCHS", "epochs.json"),
    ]:
        monkeypatch.setattr(L, attr, tmp_path / name)


def test_detect_regime_opens_new_epoch_after_sustained_shift(tmp_path, monkeypatch):
    _point_paths_to_tmp(tmp_path, monkeypatch)
    # Establish an e1 baseline of ~100k via history.
    for _ in range(3):
        L.append_jsonl(L.CALIBRATION_HISTORY, {"epoch_id": "e1", "five_hour": {"confidence": "ok", "cap_wtok": 100000}})
    epochs = {"epochs": [{"id": "e1", "start_ts": 0}], "current": "e1", "regime_streak": 0}
    epoch = epochs["epochs"][0]
    shifted = {
        "five_hour": {"confidence": "ok", "cap_wtok": 200000},  # +100% vs baseline
        "seven_day": {"confidence": "none", "cap_wtok": None},
    }

    epochs, ep, r1 = C._detect_regime(epochs, epoch, shifted, 1000)
    epochs, ep, r2 = C._detect_regime(epochs, ep, shifted, 1000)
    epochs, ep, r3 = C._detect_regime(epochs, ep, shifted, 1000)
    assert r1 is None and r2 is None  # streak building (< REGIME_CONFIRM)
    assert r3 is not None  # 3rd consecutive shift => new epoch
    assert epochs["current"] == "e2"
    assert ep["start_ts"] == 1000  # new epoch anchored at latest snapshot ts


def test_detect_regime_resets_streak_when_stable(tmp_path, monkeypatch):
    _point_paths_to_tmp(tmp_path, monkeypatch)
    for _ in range(3):
        L.append_jsonl(L.CALIBRATION_HISTORY, {"epoch_id": "e1", "five_hour": {"confidence": "ok", "cap_wtok": 100000}})
    epochs = {"epochs": [{"id": "e1", "start_ts": 0}], "current": "e1", "regime_streak": 2}
    epoch = epochs["epochs"][0]
    stable = {
        "five_hour": {"confidence": "ok", "cap_wtok": 105000},  # +5% only
        "seven_day": {"confidence": "none", "cap_wtok": None},
    }
    epochs, ep, r = C._detect_regime(epochs, epoch, stable, 1000)
    assert r is None and epochs["regime_streak"] == 0 and epochs["current"] == "e1"


def test_recompute_from_ts_does_not_mutate_state(tmp_path, monkeypatch):
    _point_paths_to_tmp(tmp_path, monkeypatch)
    for i, ts in enumerate([100, 200, 300, 400, 500, 600], start=1):
        L.append_jsonl(
            L.WTOK_EVENTS, {"ts": ts, "model": "claude-sonnet-4-6", "request_id": f"r{i}", "raw": {}, "wtok": 1000}
        )
    for i, ts in enumerate([100, 200, 300, 400, 500, 600]):
        L.append_jsonl(L.SNAPSHOTS_ARCHIVE, {"ts": ts, "five_hour": {"pct": 5 + i, "resets_at": 9999}})
    out = C.calibrate(from_ts=300, write=False)
    assert out["epoch_id"] == "recompute" and out["from_ts"] == 300
    assert not L.EPOCHS.exists() and not L.CALIBRATION_HISTORY.exists()  # untouched


def test_weights_override_changes_cap(tmp_path, monkeypatch):
    _point_paths_to_tmp(tmp_path, monkeypatch)
    # raw output-only usage; alternate weights double the output weight => 2x wtok => 2x cap.
    for i, ts in enumerate([100, 200, 300, 400, 500, 600], start=1):
        L.append_jsonl(
            L.WTOK_EVENTS,
            {
                "ts": ts,
                "model": "claude-sonnet-4-6",
                "request_id": f"r{i}",
                "raw": {"output_tokens": 200},
                "wtok": 1000,
            },
        )
    for i, ts in enumerate([100, 200, 300, 400, 500, 600]):
        L.append_jsonl(L.SNAPSHOTS_ARCHIVE, {"ts": ts, "five_hour": {"pct": 5 + i, "resets_at": 9999}})
    alt = tmp_path / "alt_weights.json"
    L.write_json(alt, {"version": "alt", "weights": {"sonnet": {"output": 10.0}}})
    base = C.calibrate(write=False)  # stored wtok (1000/event)
    rw = C.calibrate(weights_path=alt, write=False)  # 200*10 = 2000/event
    assert base["five_hour"]["cap_wtok"] and rw["five_hour"]["cap_wtok"]
    assert rw["five_hour"]["cap_wtok"] == 2 * base["five_hour"]["cap_wtok"]


# ── Rollup, week anchor & forecast (P3) ──────────────────────────────────────
def test_week_anchor_tuesday_1pm_and_dst():
    # Wed 2026-06-03 (EDT) -> Tue 2026-06-02 13:00 -04:00
    assert L.week_start_key(_epoch(2026, 6, 3, 20)) == "2026-06-02T13:00:00-04:00"
    # Monday belongs to the PRIOR Tuesday week
    assert L.week_start_key(_epoch(2026, 6, 1, 12)) == "2026-05-26T13:00:00-04:00"
    # Winter date resolves to EST (-05:00) — DST handled
    assert L.week_start_key(_epoch(2026, 1, 15, 18)) == "2026-01-13T13:00:00-05:00"


def test_rollup_buckets_sum(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "WTOK_EVENTS", tmp_path / "wtok_events.jsonl")
    monkeypatch.setattr(L, "CALIBRATED_CAPS", tmp_path / "caps.json")
    # Two events same day, one a week later.
    L.append_jsonl(
        L.WTOK_EVENTS, {"ts": _epoch(2026, 6, 3, 15), "session_id": "s1", "model": "claude-opus-4-8", "wtok": 1000}
    )
    L.append_jsonl(
        L.WTOK_EVENTS, {"ts": _epoch(2026, 6, 3, 17), "session_id": "s1", "model": "claude-sonnet-4-6", "wtok": 500}
    )
    L.append_jsonl(
        L.WTOK_EVENTS, {"ts": _epoch(2026, 6, 10, 15), "session_id": "s2", "model": "claude-sonnet-4-6", "wtok": 700}
    )
    r = R.build_rollup()
    assert r["daily"]["2026-06-03"]["wtok"] == 1500 and r["daily"]["2026-06-03"]["events"] == 2
    assert r["monthly"]["2026-06"]["wtok"] == 2200
    assert r["sessions"]["s1"]["wtok"] == 1500
    # Two distinct weekly buckets (Jun-02 and Jun-09 anchors)
    assert len(r["weekly"]) == 2
    # per-model split in the first week
    wk1 = "2026-06-02T13:00:00-04:00"
    assert r["weekly_by_model"][wk1]["opus"] == 1000
    assert r["weekly_by_model"][wk1]["sonnet"] == 500


def test_forecast_cap_before_reset():
    T = 100000
    latest = {"ts": T, "five_hour": {"resets_at": T + 7200}}  # resets in 2h
    # window started 3h ago (5h window): used 900k of 1M => burn 300k/hr => cap in 0.33h
    fc = C._forecast("five_hour", latest, used_wtok=900000, cap_wtok=1000000)
    assert fc["burn_wtok_per_hr"] == 300000
    assert fc["time_to_cap_hr"] == 0.33
    assert fc["hours_to_reset"] == 2.0
    assert fc["verdict"] == "cap_before_reset"


def test_forecast_coasts_to_reset():
    T = 100000
    latest = {"ts": T, "five_hour": {"resets_at": T + 7200}}
    # low usage => time_to_cap >> hours_to_reset => verdict ok
    fc = C._forecast("five_hour", latest, used_wtok=30000, cap_wtok=1000000)
    assert fc["verdict"] == "ok"


# ── Dashboard (P4) ───────────────────────────────────────────────────────────
import usage_dashboard as D  # noqa: E402


def test_dashboard_builds_with_empty_artifacts(tmp_path, monkeypatch):
    # All artifacts missing -> still renders a valid report, no crash.
    _point_paths_to_tmp(tmp_path, monkeypatch)
    monkeypatch.setattr(L, "ROLLUP", tmp_path / "rollup.json")
    md = D.build_dashboard()
    assert "# Usage Calibration Dashboard" in md
    assert "Current Windows" in md
    assert "collecting" in md or "Not enough" in md  # cold-start trend message


def test_dashboard_renders_caps_and_trend(tmp_path, monkeypatch):
    _point_paths_to_tmp(tmp_path, monkeypatch)
    monkeypatch.setattr(L, "ROLLUP", tmp_path / "rollup.json")
    L.write_json(
        L.CALIBRATED_CAPS,
        {
            "updated_at": "2026-06-03T00:00:00+00:00",
            "epoch_id": "e1",
            "weight_table_version": "2026-06-pricing",
            "five_hour": {
                "cap_wtok": 200_000_000,
                "used_wtok": 50_000_000,
                "confidence": "ok",
                "forecast": {"time_to_cap_hr": 3.0, "verdict": "ok"},
            },
            "seven_day": {"cap_wtok": 900_000_000, "used_wtok": 100_000_000, "confidence": "ok"},
        },
    )
    for cap in (180_000_000, 190_000_000, 200_000_000):
        L.append_jsonl(L.CALIBRATION_HISTORY, {"five_hour": {"cap_wtok": cap, "confidence": "ok"}})
    L.write_json(
        L.ROLLUP,
        {
            "weekly": {"2026-06-02T13:00:00-04:00": {"wtok": 50_000_000, "events": 10}},
            "monthly": {"2026-06": {"wtok": 50_000_000, "events": 10}},
        },
    )
    md = D.build_dashboard()
    assert "200.0M" in md and "xychart-beta" in md  # cap value + trend chart
    assert "| 5-hour | 50.0M | 200.0M | ok |" in md  # current-windows row
