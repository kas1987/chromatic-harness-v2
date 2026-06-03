"""Unit tests for scripts/validate_event_schema.py.

Tests validate_file() and main() using tmp_path for all file I/O.
Covers: valid log → exit 0, missing file → exit 2, invalid JSON → exit 1,
non-object record → exit 1, validate_record field errors → exit 1,
and CLI --log / --repo-root argument wiring.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "scripts" / "validate_event_schema.py"

# validate_event_schema imports common_harness via a bare `from common_harness import ...`
# so we must ensure the scripts directory is on sys.path before loading the module.
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_spec = importlib.util.spec_from_file_location("validate_event_schema", _SCRIPT)
ves = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ves)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Minimal valid event record (satisfies common_harness.validate_record)
# ---------------------------------------------------------------------------

_VALID_RECORD = {
    "event_id": "evt_20260601_120000_abc123",
    "timestamp": "2026-06-01T12:00:00Z",
    "repo": "chromatic-harness-v2",
    "source": {"surface": "terminal"},
    "event_type": "info",
    "severity": "low",
    "category": "manual_note",
    "status": "open",
}


# ---------------------------------------------------------------------------
# validate_file
# ---------------------------------------------------------------------------


def test_validate_file_returns_0_for_valid_log(tmp_path):
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps(_VALID_RECORD) + "\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 0


def test_validate_file_returns_2_for_missing_file(tmp_path):
    rc = ves.validate_file(tmp_path / "absent.jsonl")
    assert rc == 2


def test_validate_file_returns_1_for_invalid_json_line(tmp_path):
    log = tmp_path / "events.jsonl"
    log.write_text("NOT JSON\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 1


def test_validate_file_returns_1_for_non_object_record(tmp_path):
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps(["a", "b"]) + "\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 1


def test_validate_file_returns_1_for_missing_required_field(tmp_path):
    bad = dict(_VALID_RECORD)
    del bad["event_id"]
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 1


def test_validate_file_returns_1_for_invalid_severity(tmp_path):
    bad = dict(_VALID_RECORD)
    bad["severity"] = "super-critical"
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 1


def test_validate_file_returns_1_for_invalid_event_type(tmp_path):
    bad = dict(_VALID_RECORD)
    bad["event_type"] = "not_a_real_type"
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 1


def test_validate_file_skips_blank_lines(tmp_path):
    log = tmp_path / "events.jsonl"
    log.write_text("\n" + json.dumps(_VALID_RECORD) + "\n\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 0


def test_validate_file_returns_0_for_multiple_valid_records(tmp_path):
    log = tmp_path / "events.jsonl"
    lines = "\n".join(json.dumps(_VALID_RECORD) for _ in range(5))
    log.write_text(lines + "\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 0


def test_validate_file_returns_1_for_invalid_source_surface(tmp_path):
    bad = dict(_VALID_RECORD)
    bad["source"] = {"surface": "not_a_surface"}
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 1


def test_validate_file_returns_1_when_source_not_dict(tmp_path):
    bad = dict(_VALID_RECORD)
    bad["source"] = "terminal"  # must be an object
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 1


def test_validate_file_returns_1_for_files_touched_not_list(tmp_path):
    bad = dict(_VALID_RECORD)
    bad["files_touched"] = "single_file.py"  # must be array
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 1


def test_validate_file_returns_0_when_files_touched_is_list(tmp_path):
    good = dict(_VALID_RECORD)
    good["files_touched"] = ["scripts/foo.py", "tests/bar.py"]
    log = tmp_path / "events.jsonl"
    log.write_text(json.dumps(good) + "\n", encoding="utf-8")
    rc = ves.validate_file(log)
    assert rc == 0


# ---------------------------------------------------------------------------
# main() CLI argument wiring
# ---------------------------------------------------------------------------


def test_main_uses_default_log_path_relative_to_repo(monkeypatch, tmp_path, capsys):
    # Create a valid log at the default relative path
    default_rel = "00_META/observability/ERROR_LOG.jsonl"
    log_path = tmp_path / default_rel
    log_path.parent.mkdir(parents=True)
    log_path.write_text(json.dumps(_VALID_RECORD) + "\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["validate_event_schema.py", "--repo-root", str(tmp_path)])
    rc = ves.main()
    assert rc == 0


def test_main_with_explicit_log_path(monkeypatch, tmp_path, capsys):
    log = tmp_path / "custom.jsonl"
    log.write_text(json.dumps(_VALID_RECORD) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["validate_event_schema.py", "--log", str(log), "--repo-root", str(tmp_path)],
    )
    rc = ves.main()
    assert rc == 0


def test_main_returns_2_for_missing_log(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_event_schema.py",
            "--log",
            str(tmp_path / "absent.jsonl"),
            "--repo-root",
            str(tmp_path),
        ],
    )
    rc = ves.main()
    assert rc == 2


def test_main_returns_1_for_invalid_record(monkeypatch, tmp_path):
    log = tmp_path / "bad.jsonl"
    bad = dict(_VALID_RECORD)
    bad["severity"] = "oops"
    log.write_text(json.dumps(bad) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["validate_event_schema.py", "--log", str(log), "--repo-root", str(tmp_path)],
    )
    rc = ves.main()
    assert rc == 1
