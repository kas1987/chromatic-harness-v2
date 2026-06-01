"""OBS-008: the observability CI workflow exists and runs the 4 required checks.

Guards against the workflow drifting or being dropped from the session branch
(where every OBS PR targets) — the bug OBS-008 fixed.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WF = REPO / ".github" / "workflows" / "harness-observability-check.yml"


def _text() -> str:
    return WF.read_text(encoding="utf-8")


def test_workflow_file_exists_on_this_branch():
    assert WF.is_file(), "harness-observability-check.yml missing from .github/workflows"


def test_workflow_parses_as_yaml_when_available():
    try:
        import yaml
    except ImportError:
        return  # pyyaml not installed in this env; skip parse check
    data = yaml.safe_load(_text())
    assert "validate-harness-observability" in data["jobs"]


def test_workflow_has_expected_job_id():
    assert "validate-harness-observability:" in _text()


def test_workflow_triggers_on_pull_request():
    assert "pull_request:" in _text()


def test_workflow_compiles_scripts():
    t = _text()
    assert "compileall" in t or "py_compile" in t


def test_workflow_validates_starter_event_log():
    t = _text()
    assert "validate_event_schema.py" in t or "validate_event_log.py" in t
    assert "00_META/observability/ERROR_LOG.jsonl" in t


def test_workflow_runs_secret_scan():
    t = _text()
    assert "security_scan.py" in t or "scan_for_secrets.py" in t


def test_workflow_runs_collision_detector():
    t = _text()
    assert "detect_file_collisions.py" in t
    assert "--active-writers" in t


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
