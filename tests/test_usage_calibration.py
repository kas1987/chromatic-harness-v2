"""Tests for the usage-calibration pipeline (weight math + snapshot-delta engine)."""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import usage_calibration_lib as L  # noqa: E402
import usage_calibrate as C  # noqa: E402


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
    assert L.wtok({"input_tokens": 100000, "output_tokens": 10000},
                  "claude-opus-4-8[1m]", weights) == 750000.0
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

    # 5 evenly-spaced events of 1000 wtok each; 5h pct climbs 1%/event.
    for i, ts in enumerate([100, 200, 300, 400, 500, 600], start=1):
        L.append_jsonl(wtok, {"ts": ts, "model": "claude-sonnet-4-6",
                              "request_id": f"r{i}", "raw": {}, "wtok": 1000})
    for i, ts in enumerate([100, 200, 300, 400, 500, 600]):
        L.append_jsonl(arc, {"ts": ts, "five_hour": {"pct": 5 + i, "resets_at": 9999},
                            "seven_day": {"pct": 16, "resets_at": 8888}})

    out = C.calibrate()
    # Each step: Δwtok=1000, Δpct=1 => cap = 1000/0.01 = 100000
    assert out["five_hour"]["cap_wtok"] == 100000
    assert out["five_hour"]["confidence"] == "ok"
    assert out["seven_day"]["cap_wtok"] is None  # flat weekly => no estimate
    assert caps.exists() and edge.exists() and hist.exists()

    # Idempotent: same inputs => identical caps
    out2 = C.calibrate()
    assert out2["five_hour"]["cap_wtok"] == out["five_hour"]["cap_wtok"]
