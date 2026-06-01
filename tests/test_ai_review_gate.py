"""Tests for scripts/ai_review_gate.py (network-free, ~12 tests)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ai_review_gate import (
    FAIL_FILES,
    WARN_FILES,
    apply_override,
    classify_level,
    generate_findings,
    risk_score,
    summarize,
    write_report,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

CLEAN_METRICS = {
    "status": "ok",
    "changed_files": 3,
    "added_lines": 50,
    "deleted_lines": 10,
    "total_lines": 60,
    "files": [
        {"path": "scripts/foo.py", "added": 50, "deleted": 10},
    ],
    "todo_hits": [],
    "new_scripts": [],
    "test_files_changed": ["tests/test_foo.py"],
}

RISKY_METRICS = {
    "status": "ok",
    "changed_files": FAIL_FILES + 5,  # over hard limit
    "added_lines": 20,
    "deleted_lines": 3000,
    "total_lines": 3020,
    "files": [{"path": f"module_{i}.py", "added": 0, "deleted": 60} for i in range(FAIL_FILES + 5)],
    "todo_hits": ["TODO: fix this later", "FIXME: broken"],
    "new_scripts": ["scripts/new_tool.py"],
    "test_files_changed": [],  # no tests
}


# ---------------------------------------------------------------------------
# 1. generate_findings: clean diff -> very few findings
# ---------------------------------------------------------------------------


def test_generate_findings_clean_few():
    findings = generate_findings(CLEAN_METRICS)
    severities = {f["severity"] for f in findings}
    # No critical/error findings on a small, tested diff.
    assert "critical" not in severities
    assert "error" not in severities
    assert len(findings) <= 2


# ---------------------------------------------------------------------------
# 2. generate_findings: risky diff -> flagged
# ---------------------------------------------------------------------------


def test_generate_findings_risky_flagged():
    findings = generate_findings(RISKY_METRICS)
    rules = {f["rule"] for f in findings}
    assert "large-pr-critical" in rules
    assert "todo-fixme-added" in rules
    assert "missing-tests" in rules


# ---------------------------------------------------------------------------
# 3. generate_findings: high deletion ratio
# ---------------------------------------------------------------------------


def test_generate_findings_high_deletion_ratio():
    m = {
        **CLEAN_METRICS,
        "added_lines": 10,
        "deleted_lines": 200,
        "total_lines": 210,
        "files": [{"path": "old.py", "added": 10, "deleted": 200}],
    }
    findings = generate_findings(m)
    rules = {f["rule"] for f in findings}
    assert "high-deletion-ratio" in rules


# ---------------------------------------------------------------------------
# 4. generate_findings: additions-absent rule
# ---------------------------------------------------------------------------


def test_generate_findings_additions_absent():
    m = {
        **CLEAN_METRICS,
        "added_lines": 0,
        "deleted_lines": 50,
        "total_lines": 50,
        "todo_hits": [],
        "new_scripts": [],
        "test_files_changed": [],
    }
    findings = generate_findings(m)
    rules = {f["rule"] for f in findings}
    assert "additions-absent" in rules


# ---------------------------------------------------------------------------
# 5. risk_score: low for clean diff
# ---------------------------------------------------------------------------


def test_risk_score_low_for_clean():
    findings = generate_findings(CLEAN_METRICS)
    score = risk_score(CLEAN_METRICS, findings)
    assert 0 <= score <= 100
    assert score < 40


# ---------------------------------------------------------------------------
# 6. risk_score: high for risky diff
# ---------------------------------------------------------------------------


def test_risk_score_high_for_risky():
    findings = generate_findings(RISKY_METRICS)
    score = risk_score(RISKY_METRICS, findings)
    assert score >= 60


# ---------------------------------------------------------------------------
# 7. classify_level: thresholds
# ---------------------------------------------------------------------------


def test_classify_level_ok():
    assert classify_level(1, 5) == "ok"


def test_classify_level_warn():
    assert classify_level(WARN_FILES, 10) == "warn"


def test_classify_level_fail_files():
    assert classify_level(FAIL_FILES, 10) == "fail"


def test_classify_level_fail_score():
    assert classify_level(1, 75) == "fail"


# ---------------------------------------------------------------------------
# 8. write_report: markdown and JSON artifacts written
# ---------------------------------------------------------------------------


def test_write_report_creates_files(tmp_path, monkeypatch):
    import ai_review_gate as mod

    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "ai_review")

    result = {
        "status": "ok",
        "risk_score": 20,
        "level": "ok",
        "changed_files": 3,
        "added_lines": 50,
        "deleted_lines": 10,
        "total_lines": 60,
        "findings": [],
        "overridden": False,
        "thresholds": {"warn_files": WARN_FILES, "fail_files": FAIL_FILES},
    }
    md_path, json_path = mod.write_report(result, "20260101T000000Z")
    assert md_path.exists()
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["risk_score"] == 20
    assert "AI Review Gate Report" in md_path.read_text()


# ---------------------------------------------------------------------------
# 9. apply_override: flips fail->override-allow + logs
# ---------------------------------------------------------------------------


def test_apply_override_flips_and_logs(tmp_path, monkeypatch):
    import ai_review_gate as mod

    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "ai_review")

    result = {"level": "fail", "risk_score": 80, "findings": [], "overridden": False}
    updated = mod.apply_override(result, "hotfix approved by oncall", "alice")

    assert updated["level"] == "override-allow"
    assert updated["overridden"] is True

    overrides_path = tmp_path / "ai_review" / "overrides.jsonl"
    assert overrides_path.exists()
    record = json.loads(overrides_path.read_text().splitlines()[0])
    assert record["actor"] == "alice"
    assert record["reason"] == "hotfix approved by oncall"
    assert record["original_level"] == "fail"


# ---------------------------------------------------------------------------
# 10. apply_override: multiple overrides appended (not overwritten)
# ---------------------------------------------------------------------------


def test_apply_override_appends(tmp_path, monkeypatch):
    import ai_review_gate as mod

    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "ai_review")

    r = {"level": "fail", "risk_score": 80, "findings": [], "overridden": False}
    mod.apply_override(r, "reason1", "bob")
    mod.apply_override(r, "reason2", "carol")

    lines = (tmp_path / "ai_review" / "overrides.jsonl").read_text().splitlines()
    assert len(lines) == 2


# ---------------------------------------------------------------------------
# 11. summarize: fail-open when no artifact exists
# ---------------------------------------------------------------------------


def test_summarize_fail_open_no_artifact(tmp_path, monkeypatch):
    import ai_review_gate as mod

    monkeypatch.setattr(mod, "ARTIFACT_DIR", tmp_path / "nonexistent")

    s = mod.summarize()
    assert s["status"] == "no_scan"
    assert s["risk_score"] is None


# ---------------------------------------------------------------------------
# 12. summarize: reads latest.json correctly
# ---------------------------------------------------------------------------


def test_summarize_reads_latest(tmp_path, monkeypatch):
    import ai_review_gate as mod

    art = tmp_path / "ai_review"
    art.mkdir()
    monkeypatch.setattr(mod, "ARTIFACT_DIR", art)

    payload = {"risk_score": 55, "level": "warn", "findings": [], "overridden": False, "timestamp": "20260101T000000Z"}
    (art / "latest.json").write_text(json.dumps(payload))

    s = mod.summarize()
    assert s["status"] == "ok"
    assert s["risk_score"] == 55
    assert s["level"] == "warn"
    assert s["overridden"] is False
