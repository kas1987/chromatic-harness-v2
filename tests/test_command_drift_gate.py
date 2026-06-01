"""Tests for command_drift_gate.py (ulos / gh-107). Network-free, tmp-isolated."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("command_drift_gate", REPO / "scripts" / "command_drift_gate.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["command_drift_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def _registry(commands):
    return {"version": "0.1.0", "commands": commands}


def test_clean_when_scripts_exist(tmp_path):
    m = _mod()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "go.py").write_text("x", encoding="utf-8")
    reg = _registry([{"name": "/go", "script": "scripts/go.py", "fallback_script": None}])
    findings = m.detect_drift(reg, tmp_path)
    assert findings == []


def test_missing_script_is_high_drift(tmp_path):
    m = _mod()
    (tmp_path / "scripts").mkdir()
    reg = _registry([{"name": "/go", "script": "scripts/missing.py", "fallback_script": None}])
    findings = m.detect_drift(reg, tmp_path)
    assert len(findings) == 1
    assert findings[0]["kind"] == "missing_script"
    assert findings[0]["severity"] == "high"


def test_missing_fallback_is_high_drift(tmp_path):
    m = _mod()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "go.py").write_text("x", encoding="utf-8")
    reg = _registry([{"name": "/go", "script": "scripts/go.py", "fallback_script": "scripts/gone.py"}])
    findings = m.detect_drift(reg, tmp_path)
    assert [f["kind"] for f in findings] == ["missing_fallback"]


def test_bd_script_is_not_a_path(tmp_path):
    m = _mod()
    reg = _registry([{"name": "/queue", "script": "bd", "fallback_script": None}])
    assert m.detect_drift(reg, tmp_path) == []


def test_duplicate_name_is_high_drift(tmp_path):
    m = _mod()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "go.py").write_text("x", encoding="utf-8")
    reg = _registry(
        [
            {"name": "/go", "script": "scripts/go.py", "fallback_script": None},
            {"name": "/go", "script": "scripts/go.py", "fallback_script": None},
        ]
    )
    findings = m.detect_drift(reg, tmp_path)
    assert any(f["kind"] == "duplicate_name" for f in findings)


def test_logs_to_dir_absence_is_NOT_drift(tmp_path):
    """Missing logs_to dirs must not be flagged (runtime-generated; CI/local trap)."""
    m = _mod()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "go.py").write_text("x", encoding="utf-8")
    reg = _registry(
        [
            {
                "name": "/go",
                "script": "scripts/go.py",
                "fallback_script": None,
                "logs_to": "07_LOGS_AND_AUDIT/decisions/decision_log.jsonl",
            }
        ]
    )
    assert m.detect_drift(reg, tmp_path) == []


def test_run_gate_status_and_counts(tmp_path):
    m = _mod()
    (tmp_path / "scripts").mkdir()
    reg_path = tmp_path / "reg.yaml"
    reg_path.write_text(
        "version: 0.1.0\ncommands:\n  - name: /go\n    script: scripts/missing.py\n    fallback_script: null\n",
        encoding="utf-8",
    )
    result = m.run_gate(reg_path, tmp_path)
    assert result["status"] == "drift"
    assert result["high_severity"] == 1
    assert result["command_count"] == 1


def test_run_gate_ok_on_real_repo_registry():
    """The shipped registry must have zero drift against the real repo."""
    m = _mod()
    result = m.run_gate()  # default paths = real registry + repo root
    assert result["status"] == "ok", f"unexpected drift: {result.get('findings')}"


def test_summarize_fail_open_on_bad_path(tmp_path):
    m = _mod()
    out = m.summarize(tmp_path / "does-not-exist.yaml", tmp_path)
    # missing file -> load returns {} -> ok with 0 commands (fail-open, no crash)
    assert out["status"] in {"ok", "error"}


def test_summarize_artifact_written_to_tmp_not_production(tmp_path):
    """Artifact must go into root-relative path, not the hardcoded production dir."""
    m = _mod()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "go.py").write_text("x", encoding="utf-8")
    reg_path = tmp_path / "reg.yaml"
    reg_path.write_text(
        "version: 0.1.0\ncommands:\n  - name: /go\n    script: scripts/go.py\n    fallback_script: null\n",
        encoding="utf-8",
    )
    m.summarize(reg_path, tmp_path)
    expected = tmp_path / "07_LOGS_AND_AUDIT" / "command_drift" / "latest.json"
    assert expected.is_file(), "artifact should be written under the provided root, not the production directory"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
