"""Tests for scripts/codegraph_effectiveness_scorecard.py.

Note: codegraph_drift.py does not exist in this repo; codegraph_effectiveness_scorecard.py
is the canonical codegraph script and is tested here.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_RUNTIME = Path(__file__).resolve().parents[2] / "02_RUNTIME"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

import codegraph_effectiveness_scorecard as cg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIELDS = cg.CSV_FIELDS


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELDS)
        writer.writeheader()
        for row in rows:
            full = {f: "" for f in _FIELDS}
            full.update(row)
            writer.writerow(full)


def _ts(offset_hours: int = 0) -> str:
    t = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# _safe_float / _safe_int
# ---------------------------------------------------------------------------


class TestSafeConversions:
    def test_safe_float_none_returns_default(self):
        assert cg._safe_float(None, 99.0) == 99.0

    def test_safe_float_valid_string(self):
        assert cg._safe_float("3.14") == pytest.approx(3.14)

    def test_safe_float_invalid_returns_default(self):
        assert cg._safe_float("not_a_number", 0.0) == 0.0

    def test_safe_float_empty_string_returns_default(self):
        assert cg._safe_float("", 5.0) == 5.0

    def test_safe_int_none_returns_default(self):
        assert cg._safe_int(None, 7) == 7

    def test_safe_int_valid_int(self):
        assert cg._safe_int(42) == 42

    def test_safe_int_valid_float_string(self):
        assert cg._safe_int("3.9") == 3

    def test_safe_int_invalid_returns_default(self):
        assert cg._safe_int("bad", 0) == 0


# ---------------------------------------------------------------------------
# _parse_dt
# ---------------------------------------------------------------------------


class TestParseDt:
    def test_parses_z_suffix(self):
        result = cg._parse_dt("2026-06-01T10:00:00Z")
        assert result is not None
        assert result.tzinfo is not None

    def test_parses_iso_format(self):
        result = cg._parse_dt("2026-06-01T10:00:00+00:00")
        assert result is not None

    def test_returns_none_for_empty(self):
        assert cg._parse_dt("") is None

    def test_returns_none_for_invalid(self):
        assert cg._parse_dt("not-a-date") is None

    def test_returns_none_for_none_input(self):
        assert cg._parse_dt(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _median
# ---------------------------------------------------------------------------


class TestMedian:
    def test_empty_returns_zero(self):
        assert cg._median([]) == 0.0

    def test_single_element(self):
        assert cg._median([42]) == 42.0

    def test_even_elements(self):
        assert cg._median([1, 3]) == pytest.approx(2.0)

    def test_odd_elements(self):
        assert cg._median([1, 2, 3, 4, 5]) == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# _pct_change
# ---------------------------------------------------------------------------


class TestPctChange:
    def test_improvement(self):
        # 50% improvement (without=100 → with=50)
        assert cg._pct_change(50, 100) == pytest.approx(50.0)

    def test_zero_without_returns_zero(self):
        assert cg._pct_change(50, 0) == 0.0

    def test_no_change(self):
        assert cg._pct_change(100, 100) == pytest.approx(0.0)

    def test_regression(self):
        # with is worse than without
        result = cg._pct_change(150, 100)
        assert result < 0


# ---------------------------------------------------------------------------
# _read_rows
# ---------------------------------------------------------------------------


class TestReadRows:
    def test_empty_csv_returns_no_rows(self, tmp_path, monkeypatch):
        csv_path = tmp_path / "runs.csv"
        _write_csv(csv_path, [])
        monkeypatch.setattr(cg, "CSV_PATH", csv_path)
        rows = cg._read_rows(14)
        assert rows == []

    def test_recent_rows_returned(self, tmp_path, monkeypatch):
        csv_path = tmp_path / "runs.csv"
        monkeypatch.setattr(cg, "CSV_PATH", csv_path)
        _write_csv(
            csv_path,
            [
                {
                    "timestamp_utc": _ts(1),
                    "task_id": "t1",
                    "mode": "with",
                    "duration_sec": "90",
                    "discovery_calls": "3",
                    "tokens": "100000",
                    "cost_usd": "0.50",
                }
            ],
        )
        rows = cg._read_rows(14)
        assert len(rows) == 1
        assert rows[0].task_id == "t1"
        assert rows[0].mode == "with"

    def test_old_rows_excluded(self, tmp_path, monkeypatch):
        csv_path = tmp_path / "runs.csv"
        monkeypatch.setattr(cg, "CSV_PATH", csv_path)
        _write_csv(
            csv_path,
            [
                {
                    "timestamp_utc": _ts(24 * 30),  # 30 days old
                    "task_id": "old",
                    "mode": "with",
                    "duration_sec": "90",
                    "discovery_calls": "2",
                    "tokens": "50000",
                    "cost_usd": "0.25",
                }
            ],
        )
        rows = cg._read_rows(14)
        assert rows == []

    def test_missing_csv_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cg, "CSV_PATH", tmp_path / "nonexistent.csv")
        assert cg._read_rows(14) == []

    def test_precision_recall_parsed(self, tmp_path, monkeypatch):
        csv_path = tmp_path / "runs.csv"
        monkeypatch.setattr(cg, "CSV_PATH", csv_path)
        _write_csv(
            csv_path,
            [
                {
                    "timestamp_utc": _ts(1),
                    "task_id": "t2",
                    "mode": "without",
                    "duration_sec": "120",
                    "discovery_calls": "8",
                    "tokens": "200000",
                    "cost_usd": "1.0",
                    "impact_precision": "0.85",
                    "impact_recall": "0.90",
                }
            ],
        )
        rows = cg._read_rows(14)
        assert rows[0].impact_precision == pytest.approx(0.85)
        assert rows[0].impact_recall == pytest.approx(0.90)


# ---------------------------------------------------------------------------
# _build_summary
# ---------------------------------------------------------------------------


class TestBuildSummary:
    def _make_rows(self) -> list[cg.RunRow]:
        return [
            cg.RunRow(
                timestamp_utc=_ts(1),
                task_id="task-1",
                task_type="arch",
                mode="with",
                duration_sec=90.0,
                discovery_calls=3,
                tokens=100_000,
                cost_usd=0.50,
                impact_precision=0.9,
                impact_recall=0.8,
                notes="",
            ),
            cg.RunRow(
                timestamp_utc=_ts(2),
                task_id="task-1",
                task_type="arch",
                mode="without",
                duration_sec=150.0,
                discovery_calls=10,
                tokens=250_000,
                cost_usd=1.20,
                impact_precision=0.7,
                impact_recall=0.6,
                notes="",
            ),
        ]

    def test_summary_structure(self):
        summary = cg._build_summary(self._make_rows(), 14)
        assert "rows_total" in summary
        assert "rows_with" in summary
        assert "rows_without" in summary
        assert "medians" in summary
        assert "improvements_pct" in summary

    def test_row_counts(self):
        summary = cg._build_summary(self._make_rows(), 14)
        assert summary["rows_total"] == 2
        assert summary["rows_with"] == 1
        assert summary["rows_without"] == 1

    def test_paired_task_ids(self):
        summary = cg._build_summary(self._make_rows(), 14)
        assert "task-1" in summary["paired_task_ids"]
        assert summary["paired_count"] == 1

    def test_duration_improvement_positive(self):
        summary = cg._build_summary(self._make_rows(), 14)
        assert summary["improvements_pct"]["duration_sec"] > 0

    def test_empty_rows_returns_zeros(self):
        summary = cg._build_summary([], 14)
        assert summary["rows_total"] == 0
        assert summary["improvements_pct"]["duration_sec"] == 0.0

    def test_no_paired_when_no_overlap(self):
        rows = [
            cg.RunRow(
                timestamp_utc=_ts(1),
                task_id="with-only",
                task_type="",
                mode="with",
                duration_sec=90.0,
                discovery_calls=3,
                tokens=100_000,
                cost_usd=0.5,
                impact_precision=None,
                impact_recall=None,
                notes="",
            ),
            cg.RunRow(
                timestamp_utc=_ts(1),
                task_id="without-only",
                task_type="",
                mode="without",
                duration_sec=150.0,
                discovery_calls=10,
                tokens=250_000,
                cost_usd=1.2,
                impact_precision=None,
                impact_recall=None,
                notes="",
            ),
        ]
        summary = cg._build_summary(rows, 14)
        assert summary["paired_count"] == 0


# ---------------------------------------------------------------------------
# _markdown
# ---------------------------------------------------------------------------


class TestMarkdown:
    def test_includes_header(self):
        summary = cg._build_summary([], 7)
        md = cg._markdown(summary)
        assert "CodeGraph Effectiveness Scorecard" in md

    def test_includes_window_days(self):
        summary = cg._build_summary([], 30)
        md = cg._markdown(summary)
        assert "window_days: 30" in md

    def test_includes_none_paired(self):
        summary = cg._build_summary([], 14)
        md = cg._markdown(summary)
        assert "none" in md

    def test_includes_paired_task_ids(self):
        rows = [
            cg.RunRow(
                timestamp_utc=_ts(1),
                task_id="shared-task",
                task_type="",
                mode="with",
                duration_sec=80.0,
                discovery_calls=2,
                tokens=90_000,
                cost_usd=0.40,
                impact_precision=None,
                impact_recall=None,
                notes="",
            ),
            cg.RunRow(
                timestamp_utc=_ts(1),
                task_id="shared-task",
                task_type="",
                mode="without",
                duration_sec=140.0,
                discovery_calls=9,
                tokens=220_000,
                cost_usd=1.0,
                impact_precision=None,
                impact_recall=None,
                notes="",
            ),
        ]
        summary = cg._build_summary(rows, 14)
        md = cg._markdown(summary)
        assert "shared-task" in md


# ---------------------------------------------------------------------------
# _ensure_csv
# ---------------------------------------------------------------------------


class TestEnsureCsv:
    def test_creates_csv_with_header(self, tmp_path, monkeypatch):
        csv_path = tmp_path / "runs.csv"
        monkeypatch.setattr(cg, "CSV_PATH", csv_path)
        monkeypatch.setattr(cg, "OUT_DIR", tmp_path)
        cg._ensure_csv()
        assert csv_path.is_file()
        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            assert list(reader.fieldnames) == cg.CSV_FIELDS

    def test_does_not_overwrite_existing(self, tmp_path, monkeypatch):
        csv_path = tmp_path / "runs.csv"
        monkeypatch.setattr(cg, "CSV_PATH", csv_path)
        monkeypatch.setattr(cg, "OUT_DIR", tmp_path)
        # Write custom content first
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text("custom_header\n", encoding="utf-8")
        cg._ensure_csv()
        assert csv_path.read_text(encoding="utf-8") == "custom_header\n"
