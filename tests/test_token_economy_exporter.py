"""BEAD B8: token economy exporter (dashboards/exporter/token_economy_exporter.py).

Feeds a sample ``ledger.jsonl`` + ``forecast_latest.json`` and asserts that:
  * the canonical ``chromatic_*`` series names are emitted (Prometheus + JSON),
  * the 3-column weekly P&L carries Axis P quota %, Axis D API $, Axis F local $,
  * the utilization gauge inverts risk against the 90% line,
  * the per-cost-center ROI table aggregates by ledger ``cost_center``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_EXPORTER = _REPO / "dashboards" / "exporter"
if str(_EXPORTER) not in sys.path:
    sys.path.insert(0, str(_EXPORTER))

import token_economy_exporter as tee  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture
def forecast_file(tmp_path: Path) -> Path:
    data = {
        "generated_at": "2026-05-30T17:53:12+00:00",
        "axis_prepaid": {
            "weekly_quota_pct": 62.0,
            "target_pct": 90.0,
            "projected_close_pct": 74.0,
            "reset_at": "2026-06-02T00:00:00+00:00",
        },
    }
    p = tmp_path / "forecast_latest.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def ledger_file(tmp_path: Path) -> Path:
    rows = [
        # Axis D — dollar-billed API spend.
        {
            "decision_id": "d1",
            "ts": "2026-05-30T10:00:00+00:00",
            "axis": "D",
            "cost_center": {
                "repo": "harness",
                "agent": "router",
                "model": "gemini-pro",
            },
            "tokens": 10000,
            "usd": 0.25,
            "quota_delta_pct": None,
            "source": "routes",
            "confidence": "known",
        },
        {
            "decision_id": "d2",
            "ts": "2026-05-30T10:05:00+00:00",
            "axis": "D",
            "cost_center": {
                "repo": "harness",
                "agent": "router",
                "model": "gemini-pro",
            },
            "tokens": 5000,
            "usd": 0.15,
            "quota_delta_pct": None,
            "source": "routes",
            "confidence": "unknown",
        },
        # Axis F — free local offload ($-equivalent).
        {
            "decision_id": "f1",
            "ts": "2026-05-30T10:10:00+00:00",
            "axis": "F",
            "cost_center": {"repo": "harness", "agent": "worker", "model": "llama3"},
            "tokens": 20000,
            "usd": 0.40,
            "quota_delta_pct": None,
            "source": "routes",
            "confidence": "known",
        },
        # Axis P — prepaid native Claude ($-equivalent, not billed).
        {
            "decision_id": "p1",
            "ts": "2026-05-30T10:15:00+00:00",
            "axis": "P",
            "cost_center": {
                "repo": "harness",
                "agent": "orchestrator",
                "model": "opus",
            },
            "tokens": 30000,
            "usd": 1.20,
            "quota_delta_pct": 0.5,
            "source": "today",
            "confidence": "known",
        },
    ]
    p = tmp_path / "ledger.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


# ── Report math ───────────────────────────────────────────────────────────--
def test_report_pnl_three_axes(forecast_file: Path, ledger_file: Path) -> None:
    report = tee.build_report(tee.load_forecast(forecast_file), tee.load_ledger(ledger_file))
    # Axis P = prepaid quota % from the forecast block.
    assert report.pnl.axis_p_quota_pct == 62.0
    # Axis D = sum of dollar-billed rows (0.25 + 0.15).
    assert report.pnl.axis_d_api_usd == 0.40
    # Axis F = free-local $-equivalent offload value.
    assert report.pnl.axis_f_local_offload_usd == 0.40
    # Axis P usd is excluded from the billed cost estimate.
    assert report.cost_estimate_usd == 0.40


def test_utilization_gauge_inverted_risk(forecast_file: Path, ledger_file: Path) -> None:
    report = tee.build_report(tee.load_forecast(forecast_file), tee.load_ledger(ledger_file))
    assert report.gauge.target_pct == 90.0
    assert report.gauge.projected_close_pct == 74.0
    # Inverted risk: projected close < 90% line => RED (under-utilization).
    assert report.gauge.status == "red"
    assert report.gauge.gap_to_target_pct == 16.0


def test_cost_center_roi_table(forecast_file: Path, ledger_file: Path) -> None:
    report = tee.build_report(tee.load_forecast(forecast_file), tee.load_ledger(ledger_file))
    keys = {cc.key for cc in report.cost_centers}
    assert "harness/router/gemini-pro" in keys
    # The two gemini-pro Axis-D rows aggregate into one cost center.
    gemini = next(cc for cc in report.cost_centers if cc.key == "harness/router/gemini-pro")
    assert gemini.usd == 0.40
    assert gemini.tokens == 15000
    assert gemini.events == 2
    assert gemini.usd_per_1k_tokens > 0


def test_unknown_band_carried(forecast_file: Path, ledger_file: Path) -> None:
    report = tee.build_report(tee.load_forecast(forecast_file), tee.load_ledger(ledger_file))
    # 1 of 4 rows is unknown => 25%.
    assert report.unknown_pct == 25.0


# ── Renderers ─────────────────────────────────────────────────────────────--
def test_prometheus_series_names(forecast_file: Path, ledger_file: Path) -> None:
    text = tee.export(forecast_path=forecast_file, ledger_path=ledger_file, fmt="prometheus")
    for name in (
        tee.METRIC_COST_ESTIMATE,
        tee.METRIC_QUOTA_PCT,
        tee.METRIC_QUOTA_TARGET,
        tee.METRIC_QUOTA_PROJECTED,
        tee.METRIC_PNL_QUOTA,
        tee.METRIC_PNL_API_USD,
        tee.METRIC_PNL_LOCAL_USD,
        tee.METRIC_ROI_USD,
        tee.METRIC_ROI_TOKENS,
        tee.METRIC_UNKNOWN_PCT,
    ):
        assert name in text
    # Grafana README explicitly names this series.
    assert "chromatic_model_cost_estimate" in text
    # Per-cost-center rows carry labels.
    assert 'cost_center="harness/router/gemini-pro"' in text


def test_json_shape_has_pnl_columns(forecast_file: Path, ledger_file: Path) -> None:
    payload = json.loads(tee.export(forecast_path=forecast_file, ledger_path=ledger_file, fmt="json"))
    pnl = payload["weekly_pnl"]
    assert set(pnl) == {
        "axis_p_quota_pct",
        "axis_d_api_usd",
        "axis_f_local_offload_usd",
    }
    assert payload["utilization_gauge"]["status"] == "red"
    assert payload["cost_center_roi"]
    assert tee.METRIC_COST_ESTIMATE in payload["metrics"]


def test_fallback_without_axis_prepaid(tmp_path: Path, ledger_file: Path) -> None:
    """Runnable against today's contract: no axis_prepaid block present."""
    forecast = {
        "generated_at": "2026-05-30T00:00:00+00:00",
        "limits": {
            "weekly": {
                "cap_usd": 100.0,
                "current_usd": 50.0,
                "target_policy": {"target_default_pct": 90.0},
            }
        },
        "forecast": {"weekly_utilization_forecast": 0.7},
    }
    fp = tmp_path / "forecast_latest.json"
    fp.write_text(json.dumps(forecast), encoding="utf-8")
    report = tee.build_report(tee.load_forecast(fp), tee.load_ledger(ledger_file))
    assert report.gauge.current_pct == 50.0
    # 0.7 fraction normalized to 70% < 90% => RED.
    assert report.gauge.projected_close_pct == 70.0
    assert report.gauge.status == "red"
