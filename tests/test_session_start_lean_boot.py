"""Tests for the opt-in lean boot path in session_start (forecast cache + token-loop gate)."""

import importlib.util
import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("session_start", _REPO / "scripts" / "session_start.py")
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)  # type: ignore


def test_lean_boot_off_by_default(monkeypatch):
    monkeypatch.delenv("CHROMATIC_LEAN_BOOT", raising=False)
    assert ss._lean_boot() is False


def test_lean_boot_env_on(monkeypatch):
    monkeypatch.setenv("CHROMATIC_LEAN_BOOT", "1")
    assert ss._lean_boot() is True


def test_is_fresh_true_for_new_file(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{}", encoding="utf-8")
    assert ss._is_fresh(p, hours=6) is True


def test_is_fresh_false_for_old_file(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{}", encoding="utf-8")
    old = time.time() - 7 * 3600
    import os

    os.utime(p, (old, old))
    assert ss._is_fresh(p, hours=6) is False


def test_is_fresh_false_for_missing():
    assert ss._is_fresh(Path("/nope/missing.json")) is False


def test_forecast_line_from_cache(tmp_path, monkeypatch):
    snap = {
        "boot": {"estimated_tokens": 1447},
        "burn": {
            "daily_spent_usd": 1.0,
            "weekly_spent_usd": 2.0,
            "weekly_trend_pct": 0.0,
        },
        "forecast": {
            "risk_level": "green",
            "end_of_day_usd": 3.0,
            "end_of_week_usd": 4.0,
            "end_of_month_usd": 5.0,
        },
        "limits": {"weekly": {"current_usd": 1.0, "cap_usd": 100.0}},
        "model_usage": {},
    }
    p = tmp_path / "forecast_latest.json"
    p.write_text(json.dumps(snap), encoding="utf-8")
    monkeypatch.setattr(ss, "_FORECAST_LATEST", p)
    line = ss._forecast_line_from_cache()
    assert line is not None
    assert "boot 1,447t" in line and "[G]" in line


def test_forecast_line_none_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "_FORECAST_LATEST", tmp_path / "absent.json")
    assert ss._forecast_line_from_cache() is None
