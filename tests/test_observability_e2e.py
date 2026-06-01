"""E2E smoke tests for the observability gate (Phase 5).

Exercises the two CLI scripts the CI gate depends on end-to-end via
subprocess, plus a well-formedness check on the committed event schema.
Mirrors the CI steps in .github/workflows/ci.yml so the pre-push E2E gate
catches regressions before they reach the runner.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"
_SCHEMA = _REPO / "00_META" / "observability" / "HARNESS_EVENT_SCHEMA.json"

PY = sys.executable


def _run(script_name: str, *cli_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, str(_SCRIPTS / script_name), *cli_args],
        capture_output=True,
        text=True,
    )


def _valid_event() -> dict:
    return {
        "event_id": "evt_e2e",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "event_type": "error",
        "severity": "high",
        "category": "tool_failure",
        "message": "boom",
        "source": {"surface": "ci"},
        "status": "open",
    }


def test_harness_event_schema_is_well_formed_json():
    assert _SCHEMA.exists(), f"missing schema: {_SCHEMA}"
    data = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_validate_event_log_empty_log_passes(tmp_path):
    """A clean (empty) log validates — matches the CI seed-then-validate path."""
    log = tmp_path / "ERROR_LOG.jsonl"
    log.touch()
    proc = _run("validate_event_log.py", "--log", str(log))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Validation passed" in proc.stdout


def test_validate_event_log_valid_line_passes(tmp_path):
    log = tmp_path / "ERROR_LOG.jsonl"
    log.write_text(json.dumps(_valid_event()) + "\n", encoding="utf-8")
    proc = _run("validate_event_log.py", "--log", str(log))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Validation passed" in proc.stdout


def test_validate_event_log_malformed_line_fails(tmp_path):
    log = tmp_path / "ERROR_LOG.jsonl"
    log.write_text("{not json}\n", encoding="utf-8")
    proc = _run("validate_event_log.py", "--log", str(log))
    assert proc.returncode == 1
    assert "Validation failed" in proc.stdout


def test_detect_file_collisions_clean(tmp_path):
    writers = tmp_path / "active_writers.json"
    writers.write_text(
        json.dumps(
            {
                "writers": [
                    {"writer": "a", "files_claimed": ["x.py"]},
                    {"writer": "b", "files_claimed": ["y.py"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    proc = _run("detect_file_collisions.py", "--active-writers", str(writers))
    assert proc.returncode == 0
    assert "No collisions detected." in proc.stdout


def test_detect_file_collisions_flags_overlap(tmp_path):
    writers = tmp_path / "active_writers.json"
    writers.write_text(
        json.dumps(
            {
                "writers": [
                    {"writer": "a", "files_claimed": ["shared.py"]},
                    {"writer": "b", "files_claimed": ["shared.py"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    proc = _run("detect_file_collisions.py", "--active-writers", str(writers))
    assert proc.returncode == 2
    assert "Collisions detected:" in proc.stdout
    assert "shared.py" in proc.stdout
