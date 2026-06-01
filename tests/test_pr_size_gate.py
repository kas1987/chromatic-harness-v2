"""Tests for the PR size & change-risk gate (bead gh-60).

Covers all 5 eval requirements with synthetic metrics (no live git needed).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("pr_size_gate", REPO / "scripts" / "pr_size_gate.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _metrics(files, added, deleted):
    return {
        "status": "ok",
        "files": files,
        "changed_files": len(files),
        "added_lines": added,
        "deleted_lines": deleted,
        "total_lines": added + deleted,
    }


def test_small_clean_change_is_low_risk():
    mod = _load()
    m = _metrics([{"path": "scripts/foo.py", "added": 10, "deleted": 2}], 10, 2)
    risk = mod.assess_risk(m, strict_protected=False)
    assert risk["risk_level"] == "low"
    assert risk["protected_paths"] == []


def test_large_change_warns():
    mod = _load()
    files = [{"path": f"src/f{i}.py", "added": 30, "deleted": 0} for i in range(mod.WARN_FILES)]
    m = _metrics(files, mod.WARN_FILES * 30, 0)
    risk = mod.assess_risk(m, strict_protected=False)
    assert risk["risk_level"] == "warn"


def test_huge_change_fails():
    mod = _load()
    files = [{"path": f"src/f{i}.py", "added": 5, "deleted": 0} for i in range(mod.FAIL_FILES)]
    m = _metrics(files, mod.FAIL_FILES * 5, 0)
    risk = mod.assess_risk(m, strict_protected=False)
    assert risk["risk_level"] == "fail"


def test_protected_path_detected():
    mod = _load()
    m = _metrics([{"path": ".github/workflows/ci.yml", "added": 3, "deleted": 1}], 3, 1)
    risk = mod.assess_risk(m, strict_protected=False)
    assert ".github/workflows/ci.yml" in risk["protected_paths"]
    assert risk["risk_level"] == "warn"  # protected lifts low -> warn


def test_protected_path_fails_when_strict():
    mod = _load()
    m = _metrics([{"path": ".claude/settings.json", "added": 2, "deleted": 0}], 2, 0)
    risk = mod.assess_risk(m, strict_protected=True)
    assert risk["risk_level"] == "fail"
    assert ".claude/settings.json" in risk["protected_paths"]


def test_thresholds_present_in_output():
    mod = _load()
    m = _metrics([], 0, 0)
    risk = mod.assess_risk(m, strict_protected=False)
    t = risk["thresholds"]
    assert t["warn_files"] == mod.WARN_FILES and t["fail_files"] == mod.FAIL_FILES
    assert t["warn_lines"] == mod.WARN_LINES and t["fail_lines"] == mod.FAIL_LINES


def test_run_gate_passed_flag():
    mod = _load()
    # fail-level change -> passed False
    big = _metrics([{"path": f"f{i}.py", "added": 1, "deleted": 0} for i in range(mod.FAIL_FILES)], mod.FAIL_FILES, 0)
    risk = mod.assess_risk(big, strict_protected=False)
    assert risk["risk_level"] == "fail"


def test_artifact_written(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "pr_risk")
    result = {
        "changed_files": 3,
        "total_lines": 50,
        "risk_level": "low",
        "passed": True,
        "risk": {"protected_paths": []},
    }
    latest = mod.write_artifact(result, "20260601T000000Z")
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["risk_level"] == "low"
    assert (tmp_path / "pr_risk" / "20260601T000000Z.json").exists()


def test_summarize_fail_open(tmp_path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "none")
    s = mod.summarize()
    assert s["status"] == "no_scan"
    assert s["risk_level"] is None


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
