"""Tests for scripts/coverage_gate.py — network-free, no real coverage run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from coverage_gate import (  # noqa: E402
    COVERAGE_DROP_TOLERANCE,
    COVERAGE_MIN,
    assess,
    parse_coverage,
    summarize,
    write_artifact,
)


# ---------------------------------------------------------------------------
# 1. parse_coverage — pure function tests
# ---------------------------------------------------------------------------

PYTEST_COV_TERMINAL = """\
---------- coverage: platform linux, python 3.11 ----------
Name                      Stmts   Miss  Cover
---------------------------------------------
scripts/coverage_gate.py     80     12    85%
---------------------------------------------
TOTAL                        80     12    85%
"""

PYTEST_COV_TERMINAL_DECIMAL = """\
TOTAL                       200     10    95%
"""

COVERAGE_JSON_PAYLOAD = json.dumps({"totals": {"percent_covered": 72.3, "num_statements": 100}})


def test_parse_coverage_terminal():
    assert parse_coverage(PYTEST_COV_TERMINAL) == 85.0


def test_parse_coverage_terminal_decimal():
    assert parse_coverage(PYTEST_COV_TERMINAL_DECIMAL) == 95.0


def test_parse_coverage_json():
    assert parse_coverage(COVERAGE_JSON_PAYLOAD) == 72.3


def test_parse_coverage_plain_percent():
    assert parse_coverage("coverage: 63%") == 63.0


def test_parse_coverage_invalid_raises():
    with pytest.raises(ValueError):
        parse_coverage("no coverage info here at all")


# ---------------------------------------------------------------------------
# Helpers to build fake collect results
# ---------------------------------------------------------------------------


def _ok(pct: float) -> dict:
    return {"status": "ok", "coverage": pct, "raw": "", "exit_code": 0}


def _not_instrumented() -> dict:
    return {"status": "not_instrumented", "coverage": None, "raw": ""}


# ---------------------------------------------------------------------------
# 2. Threshold-min fail (Eval gate 1)
# ---------------------------------------------------------------------------


def test_threshold_min_fail(tmp_path, monkeypatch):
    monkeypatch.setattr("coverage_gate.ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr("coverage_gate.BASELINE_FILE", tmp_path / "baseline.json")
    monkeypatch.setattr("coverage_gate.COVERAGE_MIN", 80.0)
    monkeypatch.setattr("coverage_gate.COVERAGE_DROP_TOLERANCE", 2.0)

    result = assess(_ok(70.0))

    assert result["passed"] is False
    assert "below minimum" in result["fail_reason"]


# ---------------------------------------------------------------------------
# 3. Drop-beyond-tolerance fail (Eval gate 2)
# ---------------------------------------------------------------------------


def test_drop_beyond_tolerance_fail(tmp_path, monkeypatch):
    monkeypatch.setattr("coverage_gate.ARTIFACT_DIR", tmp_path)
    baseline_file = tmp_path / "baseline.json"
    monkeypatch.setattr("coverage_gate.BASELINE_FILE", baseline_file)
    monkeypatch.setattr("coverage_gate.COVERAGE_MIN", 0.0)
    monkeypatch.setattr("coverage_gate.COVERAGE_DROP_TOLERANCE", 2.0)

    # Write a baseline.
    baseline_file.write_text(json.dumps({"coverage": 80.0}))

    result = assess(_ok(77.0))  # dropped 3 pp > 2.0 tolerance

    assert result["passed"] is False
    assert "dropped" in result["fail_reason"]


# ---------------------------------------------------------------------------
# 4. Within-tolerance pass
# ---------------------------------------------------------------------------


def test_within_tolerance_pass(tmp_path, monkeypatch):
    monkeypatch.setattr("coverage_gate.ARTIFACT_DIR", tmp_path)
    baseline_file = tmp_path / "baseline.json"
    monkeypatch.setattr("coverage_gate.BASELINE_FILE", baseline_file)
    monkeypatch.setattr("coverage_gate.COVERAGE_MIN", 0.0)
    monkeypatch.setattr("coverage_gate.COVERAGE_DROP_TOLERANCE", 2.0)

    baseline_file.write_text(json.dumps({"coverage": 80.0}))

    result = assess(_ok(79.0))  # dropped 1 pp <= 2.0 tolerance

    assert result["passed"] is True
    assert result["fail_reason"] is None


# ---------------------------------------------------------------------------
# 5. No baseline: records current as baseline and passes
# ---------------------------------------------------------------------------


def test_no_baseline_records_and_passes(tmp_path, monkeypatch):
    monkeypatch.setattr("coverage_gate.ARTIFACT_DIR", tmp_path)
    baseline_file = tmp_path / "baseline.json"
    monkeypatch.setattr("coverage_gate.BASELINE_FILE", baseline_file)
    monkeypatch.setattr("coverage_gate.COVERAGE_MIN", 0.0)
    monkeypatch.setattr("coverage_gate.COVERAGE_DROP_TOLERANCE", 2.0)

    assert not baseline_file.exists()

    result = assess(_ok(65.0))

    assert result["passed"] is True
    assert baseline_file.exists()
    saved = json.loads(baseline_file.read_text())
    assert saved["coverage"] == 65.0


# ---------------------------------------------------------------------------
# 6. not_instrumented never false-passes
# ---------------------------------------------------------------------------


def test_not_instrumented_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("coverage_gate.ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr("coverage_gate.BASELINE_FILE", tmp_path / "baseline.json")
    monkeypatch.setattr("coverage_gate.COVERAGE_MIN", 0.0)
    monkeypatch.setattr("coverage_gate.COVERAGE_DROP_TOLERANCE", 2.0)

    result = assess(_not_instrumented())

    assert result["passed"] is False
    assert result["coverage"] is None


# ---------------------------------------------------------------------------
# 7. write_artifact writes latest.json and timestamped copy
# ---------------------------------------------------------------------------


def test_write_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("coverage_gate.ARTIFACT_DIR", tmp_path)

    payload = {"status": "ok", "passed": True, "coverage": 85.0, "baseline": 85.0}
    latest = write_artifact(payload, "20260601T000000Z")

    assert latest == tmp_path / "latest.json"
    assert latest.exists()
    timestamped = tmp_path / "coverage_20260601T000000Z.json"
    assert timestamped.exists()
    data = json.loads(latest.read_text())
    assert data["coverage"] == 85.0


# ---------------------------------------------------------------------------
# 8. summarize fail-open (no artifact)
# ---------------------------------------------------------------------------


def test_summarize_fail_open(tmp_path, monkeypatch):
    monkeypatch.setattr("coverage_gate.ARTIFACT_DIR", tmp_path)

    result = summarize()

    assert result["passed"] is True  # fail-open
    assert result["status"] == "unknown"


# ---------------------------------------------------------------------------
# 9. summarize reads latest.json
# ---------------------------------------------------------------------------


def test_summarize_reads_latest(tmp_path, monkeypatch):
    monkeypatch.setattr("coverage_gate.ARTIFACT_DIR", tmp_path)

    payload = {
        "status": "ok",
        "passed": True,
        "coverage": 90.0,
        "baseline": 88.0,
    }
    (tmp_path / "latest.json").write_text(json.dumps(payload))

    result = summarize()

    assert result["status"] == "ok"
    assert result["passed"] is True
    assert result["coverage"] == 90.0
    assert result["baseline"] == 88.0
