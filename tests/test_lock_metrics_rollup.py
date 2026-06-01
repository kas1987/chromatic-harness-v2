"""Tests for lock metrics rollup utility."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import scripts.lock_metrics_rollup as lmr
from scripts.lock_metrics_rollup import build_rollup


def _ts(offset_minutes: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).isoformat()


def test_build_rollup_counts_and_percentiles(tmp_path: Path):
    log_path = tmp_path / "WORKFLOW_RUN_LOG.jsonl"
    rows = [
        {
            "timestamp": _ts(-10),
            "event_type": "lock.acquire",
            "lock_name": "intake_queue_mutation",
            "lock_wait_ms": 20,
            "lock_attempts": 1,
        },
        {
            "timestamp": _ts(-9),
            "event_type": "lock.acquire",
            "lock_name": "intake_queue_mutation",
            "lock_wait_ms": 80,
            "lock_attempts": 2,
        },
        {
            "timestamp": _ts(-8),
            "event_type": "lock.timeout",
            "lock_name": "git_ship",
            "lock_wait_ms": 300,
            "lock_attempts": 4,
        },
        {
            "timestamp": _ts(-12000),
            "event_type": "lock.acquire",
            "lock_name": "old",
            "lock_wait_ms": 999,
            "lock_attempts": 1,
        },
    ]
    log_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    out = build_rollup(log_path=log_path, lookback_days=7)

    assert out["ok"] is True
    assert out["event_counts"]["acquire"] == 2
    assert out["event_counts"]["timeout"] == 1
    assert out["event_counts"]["total"] == 3
    assert out["wait_ms"]["p50"] in (20, 80)
    assert out["wait_ms"]["p95"] == 80
    assert out["timeout_rate"] > 0
    assert "intake_queue_mutation" in out["by_lock"]
    trend = out.get("trend_daily", [])
    assert len(trend) == 7
    assert any(day.get("acquire", 0) > 0 or day.get("timeout", 0) > 0 for day in trend)


def test_markdown_trend_rows_match_lookback_days(tmp_path: Path):
    log_path = tmp_path / "WORKFLOW_RUN_LOG.jsonl"
    rows = [
        {
            "timestamp": _ts(-10),
            "event_type": "lock.acquire",
            "lock_name": "intake_queue_mutation",
            "lock_wait_ms": 20,
            "lock_attempts": 1,
        }
    ]
    log_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    out = build_rollup(log_path=log_path, lookback_days=7)
    old_repo = lmr.REPO
    old_out = lmr.OUT_DIR
    try:
        lmr.REPO = tmp_path
        lmr.OUT_DIR = tmp_path / ".agents" / "audits" / "locks"
        paths = lmr._write_reports(out)
        md = (tmp_path / paths["markdown"]).read_text(encoding="utf-8")
    finally:
        lmr.REPO = old_repo
        lmr.OUT_DIR = old_out
    day_rows = [ln for ln in md.splitlines() if re.match(r"^\| \d{4}-\d{2}-\d{2} \|", ln)]
    assert len(day_rows) == 7
