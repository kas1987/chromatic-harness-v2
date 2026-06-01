"""Tests for scripts/arch_compliance_gate.py -- network-free."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Allow importing the script directly.
import importlib.util
import sys

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "arch_compliance_gate.py"
spec = importlib.util.spec_from_file_location("arch_compliance_gate", _SCRIPT)
_mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(_mod)  # type: ignore[union-attr]

diff_structure = _mod.diff_structure
check_compliance = _mod.check_compliance
check_drift = _mod.check_drift
write_artifact = _mod.write_artifact
summarize = _mod.summarize
EXPECTED_STRUCTURE = _mod.EXPECTED_STRUCTURE


# ---------------------------------------------------------------------------
# diff_structure -- pure function tests
# ---------------------------------------------------------------------------


def test_diff_structure_added():
    baseline = {"scripts": "dir", "docs": "dir"}
    current = {"scripts": "dir", "docs": "dir", "new_dir": "dir"}
    result = diff_structure(baseline, current)
    assert result["added"] == ["new_dir"]
    assert result["removed"] == []


def test_diff_structure_removed():
    baseline = {"scripts": "dir", "docs": "dir", "old_dir": "dir"}
    current = {"scripts": "dir", "docs": "dir"}
    result = diff_structure(baseline, current)
    assert result["added"] == []
    assert result["removed"] == ["old_dir"]


def test_diff_structure_none():
    baseline = {"scripts": "dir", "docs": "dir"}
    current = {"scripts": "dir", "docs": "dir"}
    result = diff_structure(baseline, current)
    assert result["added"] == []
    assert result["removed"] == []


# ---------------------------------------------------------------------------
# check_compliance
# ---------------------------------------------------------------------------


def test_compliance_pass(tmp_path):
    # Create every required entry.
    for name in EXPECTED_STRUCTURE:
        entry = tmp_path / name
        if "." in name:  # treat as file
            entry.write_text("x")
        else:
            entry.mkdir()
    result = check_compliance(tmp_path)
    assert result["passed"] is True
    assert result["missing"] == []


def test_compliance_fail_when_required_missing(tmp_path):
    # Create all except one.
    for name in EXPECTED_STRUCTURE[:-1]:
        entry = tmp_path / name
        if "." in name:
            entry.write_text("x")
        else:
            entry.mkdir()
    result = check_compliance(tmp_path)
    assert result["passed"] is False
    assert EXPECTED_STRUCTURE[-1] in result["missing"]


# ---------------------------------------------------------------------------
# check_drift
# ---------------------------------------------------------------------------


def test_no_baseline_creates_baseline_and_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(_mod, "BASELINE_FILE", tmp_path / "baseline.json")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs").mkdir()
    result = check_drift(tmp_path)
    assert result["passed"] is True
    assert result["status"] == "baseline_created"
    assert (tmp_path / "baseline.json").exists()


def test_drift_recorded_vs_baseline(tmp_path, monkeypatch):
    baseline_file = tmp_path / "baseline.json"
    monkeypatch.setattr(_mod, "ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(_mod, "BASELINE_FILE", baseline_file)

    # Write a baseline with only "scripts".
    baseline_file.write_text(json.dumps({"scripts": "dir"}), encoding="utf-8")

    # Current has "scripts" + "docs" (added) and lost nothing (removed=none).
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs").mkdir()

    result = check_drift(tmp_path)
    assert result["drift_detected"] is True
    assert "docs" in result["added"]
    assert result["removed"] == []
    # Default (not strict): passes even with drift.
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# write_artifact + summarize
# ---------------------------------------------------------------------------


def test_artifact_write(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "ARTIFACT_DIR", tmp_path)
    payload = {"passed": True, "compliance": {"missing": []}, "drift": {"added": [], "removed": []}}
    artifact = write_artifact(payload, "20260601T000000Z")
    assert artifact == tmp_path / "latest.json"
    data = json.loads(artifact.read_text())
    assert data["passed"] is True
    assert data["timestamp"] == "20260601T000000Z"
    assert (tmp_path / "20260601T000000Z.json").exists()


def test_summarize_fail_open(tmp_path, monkeypatch):
    # No latest.json -- should return no_scan, not raise.
    monkeypatch.setattr(_mod, "ARTIFACT_DIR", tmp_path)
    result = summarize()
    assert result["status"] == "no_scan"
    assert result["passed"] is None


def test_summarize_reads_latest(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "ARTIFACT_DIR", tmp_path)
    payload = {
        "passed": True,
        "compliance": {"missing": ["foo"]},
        "drift": {"added": ["bar"], "removed": []},
        "timestamp": "20260601T000000Z",
    }
    (tmp_path / "latest.json").write_text(json.dumps(payload), encoding="utf-8")
    result = summarize()
    assert result["status"] == "ok"
    assert result["passed"] is True
    assert result["missing"] == ["foo"]
    assert result["drift_added"] == ["bar"]
    assert result["drift_removed"] == []
