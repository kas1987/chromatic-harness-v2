"""Smoke test for the Observability v2.1 scaffold (OBS-001 / trsk.1).

Network-free, hermetic. Asserts the installed scaffold is structurally intact:
required files exist, every script byte-compiles, the event schema is valid
JSON, and the starter ERROR_LOG validates against the bundled validator.
"""

from __future__ import annotations

import json
import py_compile
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OBS = REPO / "00_META" / "observability"
SCRIPTS = REPO / "scripts"

REQUIRED_FILES = [
    OBS / "HARNESS_EVENT_SCHEMA.json",
    OBS / "ERROR_LOG.jsonl",
    OBS / "PDR_CHROMATIC_HARNESS_OBSERVABILITY_V2_1.md",
    OBS / "OBSERVABILITY_PLAYBOOK.md",
    REPO / "00_META" / "queues" / "ERROR_REMEDIATION_QUEUE.md",
    REPO / "templates" / "EVENT_RECORD_TEMPLATE.json",
    REPO / ".chromatic" / "active_writers.json",
]

OBS_SCRIPTS = [
    "common_harness.py",
    "log_harness_event.py",
    "validate_event_log.py",
    "validate_event_schema.py",
    "claim_files.py",
    "release_files.py",
    "detect_file_collisions.py",
    "harness_run.py",
    "route_event.py",
    "snapshot_git_state.py",
    "check_dirty_state.py",
    "update_last_known_good.py",
    "scan_for_secrets.py",
    "redact_secrets.py",
    "find_event.py",
    "update_event_status.py",
    "generate_observability_report.py",
    "propose_learnings.py",
    "summarize_error_patterns.py",
    "bootstrap_observability.py",
]


def test_required_scaffold_files_exist():
    missing = [str(p.relative_to(REPO)) for p in REQUIRED_FILES if not p.is_file()]
    assert not missing, f"missing scaffold files: {missing}"


def test_all_observability_scripts_present_and_compile():
    for name in OBS_SCRIPTS:
        p = SCRIPTS / name
        assert p.is_file(), f"missing script: scripts/{name}"
        py_compile.compile(str(p), doraise=True)


def test_event_schema_is_valid_json():
    schema = json.loads((OBS / "HARNESS_EVENT_SCHEMA.json").read_text(encoding="utf-8"))
    assert isinstance(schema, dict) and schema, "schema must be a non-empty JSON object"


def test_starter_error_log_validates():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "validate_event_log.py"), "--log", str(OBS / "ERROR_LOG.jsonl")],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"ERROR_LOG failed validation:\n{result.stdout}\n{result.stderr}"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
