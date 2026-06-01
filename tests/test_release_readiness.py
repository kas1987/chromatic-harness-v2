"""Tests for scripts/release_readiness.py — network-free, no real artifacts read."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

# Ensure scripts/ is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from release_readiness import (  # noqa: E402
    collect_blockers,
    coverage_summary,
    load_inputs,
    make_report,
    quality_score,
    security_score,
    summarize,
    write_artifact,
    ARTIFACT_DIR,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_PASS_INPUTS = {
    "security": {"passed": True, "high_severity_total": 0},
    "coverage": {"passed": True, "coverage": 85.0, "baseline": 80.0},
    "pr_risk": {"passed": True, "risk_level": "low"},
    "preflight": {"passed": True, "stages": []},
    "arch": {"passed": True},
}

FAILING_INPUTS = {
    "security": {"passed": False, "high_severity_total": 3},
    "coverage": {"passed": False, "coverage": 50.0, "baseline": 80.0},
    "pr_risk": {"passed": False, "risk_level": "fail"},
    "preflight": {"passed": False, "stages": []},
    "arch": {"passed": False},
}


# ---------------------------------------------------------------------------
# quality_score
# ---------------------------------------------------------------------------


def test_quality_score_all_pass():
    score = quality_score(ALL_PASS_INPUTS)
    assert score == 100  # 40 + 35 + 25


def test_quality_score_all_fail():
    score = quality_score(FAILING_INPUTS)
    assert score == 0


def test_quality_score_partial():
    inputs = {
        "preflight": {"passed": True},
        "coverage": {"passed": False},
        "arch": {"passed": True},
    }
    # preflight 40 + arch 25 = 65
    assert quality_score(inputs) == 65


# ---------------------------------------------------------------------------
# security_score
# ---------------------------------------------------------------------------


def test_security_score_clean():
    sec = {"passed": True, "high_severity_total": 0}
    assert security_score(sec) == 100


def test_security_score_high_sev_penalized():
    sec = {"passed": True, "high_severity_total": 2}
    # Default penalty 25 per finding => 100 - 50 = 50
    score = security_score(sec)
    assert score == 50


def test_security_score_failed_gate():
    sec = {"passed": False, "high_severity_total": 0}
    assert security_score(sec) == 0


def test_security_score_missing():
    assert security_score({"_missing": True}) == 0


def test_security_score_floor_zero():
    sec = {"passed": True, "high_severity_total": 10}
    # 100 - 10*25 = -150 => floor 0
    assert security_score(sec) == 0


# ---------------------------------------------------------------------------
# collect_blockers
# ---------------------------------------------------------------------------


def test_collect_blockers_none():
    blockers = collect_blockers(ALL_PASS_INPUTS)
    # bd may or may not be available; gate failures must be empty
    gate_blockers = [b for b in blockers if b["gate"] != "bead"]
    assert gate_blockers == []


def test_collect_blockers_all_failing():
    blockers = collect_blockers(FAILING_INPUTS)
    gates = {b["gate"] for b in blockers}
    assert "security" in gates
    assert "coverage" in gates
    assert "preflight" in gates
    assert "arch" in gates
    assert "pr_risk" in gates


def test_collect_blockers_missing_files_not_blocker():
    """Missing artifacts should NOT add blockers (fail-open)."""
    inputs = {k: {"_missing": True} for k in ("security", "coverage", "pr_risk", "preflight", "arch")}
    blockers = [b for b in collect_blockers(inputs) if b["gate"] != "bead"]
    assert blockers == []


# ---------------------------------------------------------------------------
# Decision GO / NO-GO
# ---------------------------------------------------------------------------


def test_decision_go():
    report = make_report(ALL_PASS_INPUTS)
    assert report["decision"] == "GO"
    assert report["passed"] is True


def test_decision_no_go():
    report = make_report(FAILING_INPUTS)
    assert report["decision"] == "NO-GO"
    assert report["passed"] is False
    assert report["blocker_count"] >= 5  # security, coverage, pr_risk, preflight, arch


# ---------------------------------------------------------------------------
# write_artifact
# ---------------------------------------------------------------------------


def test_write_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("release_readiness.ARTIFACT_DIR", tmp_path)
    result = {"quality_score": 100, "security_score": 100, "decision": "GO", "passed": True}
    artifact = write_artifact(result, "20260101T000000Z")
    assert artifact.exists()
    data = json.loads(artifact.read_text())
    assert data["decision"] == "GO"
    assert data["timestamp"] == "20260101T000000Z"
    # Timestamped copy also written
    ts_file = tmp_path / "20260101T000000Z.json"
    assert ts_file.exists()


# ---------------------------------------------------------------------------
# summarize (fail-open)
# ---------------------------------------------------------------------------


def test_summarize_no_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("release_readiness.ARTIFACT_DIR", tmp_path)
    result = summarize()
    assert result["status"] == "no_report"
    assert result["decision"] is None


def test_summarize_ok(tmp_path, monkeypatch):
    monkeypatch.setattr("release_readiness.ARTIFACT_DIR", tmp_path)
    data = {"decision": "GO", "quality_score": 100, "security_score": 100, "blocker_count": 0}
    (tmp_path / "latest.json").write_text(json.dumps(data))
    result = summarize()
    assert result["status"] == "ok"
    assert result["decision"] == "GO"
    assert result["quality_score"] == 100


def test_summarize_corrupt_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("release_readiness.ARTIFACT_DIR", tmp_path)
    (tmp_path / "latest.json").write_text("not json {{{{")
    result = summarize()
    assert result["status"] == "error"
    assert result["decision"] is None


# ---------------------------------------------------------------------------
# load_inputs partial / missing artifact handled gracefully
# ---------------------------------------------------------------------------


def test_load_inputs_missing_files(tmp_path):
    paths = {k: tmp_path / f"{k}.json" for k in ("security", "coverage")}
    inputs = load_inputs(paths)
    assert inputs["security"]["_missing"] is True
    assert inputs["coverage"]["_missing"] is True


def test_load_inputs_corrupt_file(tmp_path):
    p = tmp_path / "security.json"
    p.write_text("{ bad json ]]]")
    inputs = load_inputs({"security": p})
    assert inputs["security"]["_missing"] is True


def test_load_inputs_valid_file(tmp_path):
    p = tmp_path / "security.json"
    p.write_text(json.dumps({"passed": True, "high_severity_total": 0}))
    inputs = load_inputs({"security": p})
    assert inputs["security"]["passed"] is True
