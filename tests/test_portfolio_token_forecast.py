"""BEAD B6: portfolio forecaster (tools/portfolio_token_forecast.py).

Asserts, against a mock ``quota_state.json`` + ``forecast_latest.json``, that:
  * the EXISTING forecast_latest.json contract is extended (not replaced) with an
    ``axis_prepaid`` block carrying {weekly_quota_pct, target_pct:90, pace_needed,
    projected_close_pct, reset_at, status},
  * the Axis P risk is INVERTED — a projected weekly close below 90% is ``red``
    (under-utilizing the prepaid asset), at/above 90% is ``green``,
  * the quota signal is read through quota_state.py's source abstraction,
  * the ROI card and Axis D $ forecast are folded into the same report.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import portfolio_token_forecast as ptf  # noqa: E402


_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=timezone.utc)


def _write_quota_state(
    path: Path, *, weekly_pct: float, captured: datetime, reset_days: float
) -> None:
    path.write_text(
        json.dumps(
            {
                "weekly_pct": weekly_pct,
                "weekly_reset": (captured + timedelta(days=reset_days)).isoformat(),
                "session_5h_pct": 12.0,
                "session_5h_reset": (captured + timedelta(hours=2)).isoformat(),
                "representative_claim": "max-20x",
                "status": "ok",
                "captured_at": captured.isoformat(),
                "source": "proxy",
            }
        ),
        encoding="utf-8",
    )


def _write_forecast_latest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "generated_at": _NOW.isoformat(),
                "forecast": {
                    "end_of_week_usd": 42.0,
                    "weekly_utilization_forecast": 0.42,
                },
                "limits": {"weekly": {"cap_usd": 100.0}},
            }
        ),
        encoding="utf-8",
    )


def _write_ledger(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"decision_id": "d1", "axis": "P", "cost_center": {"c_level": "C4"}}
                ),
                json.dumps(
                    {"decision_id": "d2", "axis": "F", "cost_center": {"c_level": "C1"}}
                ),
                json.dumps(
                    {"decision_id": "d3", "axis": "P", "cost_center": {"c_level": "C3"}}
                ),
            ]
        ),
        encoding="utf-8",
    )


def test_axis_prepaid_block_and_inverted_status_under(tmp_path: Path) -> None:
    """Low pace (10% used, 2d elapsed of 7) projects below 90% → INVERTED red."""
    qs = tmp_path / "quota_state.json"
    fc = tmp_path / "forecast_latest.json"
    led = tmp_path / "ledger.jsonl"
    # captured ~just now so the staleness guard passes (fresh signal).
    _write_quota_state(
        qs, weekly_pct=10.0, captured=_NOW - timedelta(seconds=30), reset_days=5.0
    )
    _write_forecast_latest(fc)
    _write_ledger(led)

    report = ptf.build_report(
        now=_NOW,
        quota_state_path=qs,
        ledger_path=led,
        forecast_latest_path=fc,
    )

    # Base contract preserved (extended, not replaced).
    assert report["forecast"]["end_of_week_usd"] == 42.0
    assert report["limits"]["weekly"]["cap_usd"] == 100.0

    ap = report["axis_prepaid"]
    # Required schema fields per spec §3.
    for key in (
        "weekly_quota_pct",
        "target_pct",
        "pace_needed",
        "projected_close_pct",
        "reset_at",
        "status",
    ):
        assert key in ap, f"missing axis_prepaid key: {key}"
    assert ap["target_pct"] == 90.0
    assert ap["weekly_quota_pct"] == 10.0
    assert ap["fresh"] is True
    assert ap["source"] == "proxy"
    # 10% over 2 elapsed days = 5%/day; 5 days left → ~35% close, well under 90.
    assert ap["projected_close_pct"] < 90.0
    # INVERTED: under target is RED.
    assert ap["status"] == "red"
    assert ap["pace_needed"] > 0


def test_inverted_status_green_when_on_pace(tmp_path: Path) -> None:
    """High pace (60% used, 2d elapsed) projects >=90% → INVERTED green."""
    qs = tmp_path / "quota_state.json"
    fc = tmp_path / "forecast_latest.json"
    _write_quota_state(
        qs, weekly_pct=60.0, captured=_NOW - timedelta(seconds=10), reset_days=5.0
    )
    _write_forecast_latest(fc)

    report = ptf.build_report(now=_NOW, quota_state_path=qs, forecast_latest_path=fc)
    ap = report["axis_prepaid"]
    # 60% / 2d = 30%/day; +5d → capped at 100% >= 90.
    assert ap["projected_close_pct"] >= 90.0
    assert ap["status"] == "green"


def test_stale_quota_state_marks_status_stale(tmp_path: Path) -> None:
    """A stale quota_state (>5min) yields no fresh Axis P signal → conservative."""
    qs = tmp_path / "quota_state.json"
    fc = tmp_path / "forecast_latest.json"
    _write_quota_state(
        qs, weekly_pct=40.0, captured=_NOW - timedelta(hours=1), reset_days=5.0
    )
    _write_forecast_latest(fc)

    report = ptf.build_report(now=_NOW, quota_state_path=qs, forecast_latest_path=fc)
    ap = report["axis_prepaid"]
    assert ap["fresh"] is False
    # weekly_pct present but not fresh → conservative red (under).
    assert ap["status"] == "red"


def test_roi_card_and_dollar_forecast_folded_in(tmp_path: Path) -> None:
    qs = tmp_path / "quota_state.json"
    fc = tmp_path / "forecast_latest.json"
    led = tmp_path / "ledger.jsonl"
    _write_quota_state(
        qs, weekly_pct=10.0, captured=_NOW - timedelta(seconds=30), reset_days=5.0
    )
    _write_forecast_latest(fc)
    _write_ledger(led)

    report = ptf.build_report(
        now=_NOW, quota_state_path=qs, ledger_path=led, forecast_latest_path=fc
    )

    roi = report["roi_card"]
    assert len(roi["routing_card"]) == 4
    assert roi["ledger_events_by_axis"] == {"P": 2, "F": 1}
    assert roi["ledger_rows"] == 3

    dollar = report["dollar_forecast"]
    assert dollar["axis"] == "D"

    # Variance folded via existing budget_forecast_accuracy.py (never raises).
    assert "forecast_variance" in report
