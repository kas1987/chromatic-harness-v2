"""Tests for the loop token/USD budget guard (OMH-3, scripts/loop_budget_guard.py)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import loop_budget_guard as g  # noqa: E402


def _iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def _ledger(path: Path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_empty_ledger_is_ok(tmp_path: Path):
    spend = g.sum_spend(tmp_path / "none.jsonl")
    assert spend == {"tokens": 0, "usd": 0.0, "rows": 0}


def test_sum_and_window(tmp_path: Path):
    led = tmp_path / "l.jsonl"
    now = datetime.now(timezone.utc)
    _ledger(
        led,
        [
            {"ts": _iso(now - timedelta(hours=48)), "tokens": 100, "usd": 1.0},
            {"ts": _iso(now - timedelta(hours=1)), "tokens": 50, "usd": 0.5},
        ],
    )
    assert g.sum_spend(led)["tokens"] == 150
    # window excludes the 48h-old row
    assert g.sum_spend(led, window_hours=24)["tokens"] == 50


def test_verdict_levels():
    assert g.verdict({"tokens": 0, "usd": 1.0}, max_usd=10, max_tokens=0)["level"] == "ok"
    assert g.verdict({"tokens": 0, "usd": 8.5}, max_usd=10, max_tokens=0)["level"] == "warn"
    assert g.verdict({"tokens": 0, "usd": 10.0}, max_usd=10, max_tokens=0)["level"] == "pause"
    assert g.verdict({"tokens": 5_000_000, "usd": 0}, max_usd=0, max_tokens=2_000_000)["level"] == "pause"


def test_no_ceiling_is_always_ok():
    assert g.verdict({"tokens": 9_999_999, "usd": 999.0}, max_usd=0, max_tokens=0)["level"] == "ok"


def test_cli_check_passes_with_no_ceiling():
    # bead validation command: must exit 0
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "loop_budget_guard.py"), "--check"], capture_output=True, text=True, cwd=REPO
    )
    assert r.returncode == 0


def test_cli_check_pauses_over_ceiling(tmp_path: Path):
    led = tmp_path / "l.jsonl"
    _ledger(led, [{"ts": _iso(datetime.now(timezone.utc)), "tokens": 0, "usd": 20.0}])
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "loop_budget_guard.py"), "--check", "--ledger", str(led), "--max-usd", "5"],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert r.returncode == 3 and "PAUSE" in r.stdout
