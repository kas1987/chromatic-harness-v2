"""Test the daily-audit issue-intake step: runs Stage 1 read-only and emits a
P3 drift finding when valid issues are staged but not yet in the seed ledger."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_audit():
    spec = importlib.util.spec_from_file_location("daily_harness_audit", REPO / "scripts" / "daily_harness_audit.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _setup_stage(tmp: Path, staged_records, ledger):
    (tmp / "07_LOGS_AND_AUDIT" / "issue_intake").mkdir(parents=True, exist_ok=True)
    (tmp / "07_LOGS_AND_AUDIT" / "seed_state").mkdir(parents=True, exist_ok=True)
    (tmp / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp / "scripts" / "intake_issues.py").write_text("# stub\n", encoding="utf-8")
    (tmp / "07_LOGS_AND_AUDIT" / "issue_intake" / "latest.json").write_text(
        json.dumps({"records": staged_records}), encoding="utf-8"
    )
    (tmp / "07_LOGS_AND_AUDIT" / "seed_state" / "issue_to_bead.json").write_text(json.dumps(ledger), encoding="utf-8")


def test_no_finding_when_no_intake_script(tmp_path):
    mod = _load_audit()
    result, finding = mod._issue_intake_step(tmp_path)
    assert result is None and finding is None  # script absent -> skipped cleanly


def test_drift_finding_when_unseeded(tmp_path, monkeypatch):
    mod = _load_audit()
    # Stub run_cmd so the step doesn't actually shell out to gh.
    monkeypatch.setattr(mod, "run_cmd", lambda *a, **k: {"ok": True, "stdout": "", "stderr": ""})
    _setup_stage(
        tmp_path,
        staged_records=[
            {"ext_ref": "gh-57", "valid": True},
            {"ext_ref": "gh-99", "valid": True},  # unseeded
            {"ext_ref": "gh-51", "valid": False},  # invalid, ignored
        ],
        ledger={"gh-57": "chromatic-harness-v2-j12l"},
    )
    _result, finding = mod._issue_intake_step(tmp_path)
    assert finding is not None
    assert finding["code"] == "issues_awaiting_seeding"
    assert "gh-99" in finding["message"]
    assert "gh-57" not in finding["message"]  # already seeded
    assert "gh-51" not in finding["message"]  # invalid


def test_no_finding_when_all_seeded(tmp_path, monkeypatch):
    mod = _load_audit()
    monkeypatch.setattr(mod, "run_cmd", lambda *a, **k: {"ok": True, "stdout": "", "stderr": ""})
    _setup_stage(
        tmp_path,
        staged_records=[{"ext_ref": "gh-57", "valid": True}],
        ledger={"gh-57": "chromatic-harness-v2-j12l"},
    )
    _result, finding = mod._issue_intake_step(tmp_path)
    assert finding is None


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
