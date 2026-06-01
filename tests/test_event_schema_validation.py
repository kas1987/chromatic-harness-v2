"""OBS-003: schema-backed event validation via validate_event_schema.py.

Hermetic, subprocess-based. Confirms invalid enum values, missing source
metadata, malformed JSONL, and non-object lines all fail (non-zero), while a
schema-valid event passes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALIDATOR = REPO / "scripts" / "validate_event_schema.py"

VALID = {
    "event_id": "evt_test_0001",
    "timestamp": "2026-06-01T00:00:00Z",
    "repo": "chromatic-harness-v2",
    "source": {"surface": "ci", "ide": "", "agent": "tester", "model": "", "session_id": "t"},
    "event_type": "info",
    "severity": "info",
    "category": "manual_note",
    "status": "resolved",
}


def _run(tmp_path: Path, *lines: str) -> subprocess.CompletedProcess:
    log = tmp_path / "events.jsonl"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--log", str(log)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _rec(**over) -> str:
    r = dict(VALID)
    r.update(over)
    return json.dumps(r)


def test_valid_event_passes():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        r = _run(Path(d), _rec())
        assert r.returncode == 0, r.stderr


def test_invalid_severity_fails(tmp_path):
    assert _run(tmp_path, _rec(severity="catastrophic")).returncode == 1


def test_invalid_status_fails(tmp_path):
    assert _run(tmp_path, _rec(status="bogus")).returncode == 1


def test_invalid_category_fails(tmp_path):
    assert _run(tmp_path, _rec(category="not_a_category")).returncode == 1


def test_invalid_event_type_fails(tmp_path):
    assert _run(tmp_path, _rec(event_type="explosion")).returncode == 1


def test_missing_source_metadata_fails(tmp_path):
    r = dict(VALID)
    del r["source"]
    assert _run(tmp_path, json.dumps(r)).returncode == 1


def test_bad_source_surface_fails(tmp_path):
    assert _run(tmp_path, _rec(source={"surface": "telepathy"})).returncode == 1


def test_malformed_jsonl_is_nonzero(tmp_path):
    assert _run(tmp_path, '{"event_id": "x", broken').returncode == 1


def test_non_object_line_is_nonzero(tmp_path):
    r = _run(tmp_path, "[1, 2, 3]")
    assert r.returncode == 1
    assert "must be a JSON object" in r.stderr


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
