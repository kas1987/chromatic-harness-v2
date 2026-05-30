"""Tests for harness event JSONL emitter (02_RUNTIME/console_api/harness_events.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from console_api.harness_events import emit_harness_event  # noqa: E402

REQUIRED_FIELDS = {
    "event_id",
    "timestamp",
    "task_id",
    "agent",
    "model",
    "event_type",
    "confidence_score",
    "risk_level",
    "result",
}


def _emit(tmp_path: Path, **overrides) -> None:
    defaults = dict(
        event_type="execute",
        task_id="mc-02wi",
        agent="claude-sonnet",
        model="claude-sonnet-4-6",
        confidence_score=85.0,
        risk_level="low",
        files_touched=["02_RUNTIME/console_api/harness_events.py"],
        tools_used=["Write", "Read"],
        result="passed",
        repo_root=tmp_path,
    )
    defaults.update(overrides)
    emit_harness_event(**defaults)


def _read_lines(tmp_path: Path) -> list[dict]:
    log = tmp_path / "07_LOGS_AND_AUDIT" / "harness_events.jsonl"
    if not log.exists():
        return []
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------


def test_emit_creates_jsonl_file(tmp_path: Path):
    _emit(tmp_path)
    log = tmp_path / "07_LOGS_AND_AUDIT" / "harness_events.jsonl"
    assert log.exists(), "harness_events.jsonl was not created"


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


def test_emitted_event_has_all_required_fields(tmp_path: Path):
    _emit(tmp_path)
    events = _read_lines(tmp_path)
    assert len(events) == 1
    event = events[0]
    missing = REQUIRED_FIELDS - event.keys()
    assert not missing, f"Missing required fields: {missing}"


def test_emitted_event_field_values(tmp_path: Path):
    _emit(tmp_path, task_id="TEST-001", agent="test-agent", result="failed")
    events = _read_lines(tmp_path)
    assert len(events) == 1
    e = events[0]
    assert e["task_id"] == "TEST-001"
    assert e["agent"] == "test-agent"
    assert e["result"] == "failed"
    assert e["event_type"] == "execute"
    assert e["risk_level"] == "low"
    assert e["confidence_score"] == 85.0
    # event_id must be a non-empty string (UUID format)
    assert isinstance(e["event_id"], str) and len(e["event_id"]) == 36
    # timestamp must be a non-empty string
    assert isinstance(e["timestamp"], str) and "T" in e["timestamp"]


def test_files_touched_and_tools_used_are_lists(tmp_path: Path):
    _emit(tmp_path, files_touched=["a.py", "b.py"], tools_used=["Read", "Grep"])
    events = _read_lines(tmp_path)
    e = events[0]
    assert e["files_touched"] == ["a.py", "b.py"]
    assert e["tools_used"] == ["Read", "Grep"]


# ---------------------------------------------------------------------------
# Append behaviour
# ---------------------------------------------------------------------------


def test_two_calls_append_two_lines(tmp_path: Path):
    _emit(tmp_path, task_id="A")
    _emit(tmp_path, task_id="B")
    events = _read_lines(tmp_path)
    assert len(events) == 2, f"Expected 2 events, got {len(events)}"
    assert events[0]["task_id"] == "A"
    assert events[1]["task_id"] == "B"


def test_each_event_has_unique_event_id(tmp_path: Path):
    _emit(tmp_path)
    _emit(tmp_path)
    events = _read_lines(tmp_path)
    ids = [e["event_id"] for e in events]
    assert ids[0] != ids[1], "event_id values should be unique across calls"


# ---------------------------------------------------------------------------
# Optional fields
# ---------------------------------------------------------------------------


def test_notes_included_when_provided(tmp_path: Path):
    _emit(tmp_path, notes="test run note")
    events = _read_lines(tmp_path)
    assert events[0].get("notes") == "test run note"


def test_notes_absent_when_not_provided(tmp_path: Path):
    _emit(tmp_path)
    events = _read_lines(tmp_path)
    assert "notes" not in events[0]


def test_duration_ms_included_when_provided(tmp_path: Path):
    _emit(tmp_path, duration_ms=250)
    events = _read_lines(tmp_path)
    assert events[0].get("duration_ms") == 250


# ---------------------------------------------------------------------------
# Validation guards
# ---------------------------------------------------------------------------


def test_invalid_event_type_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="event_type"):
        _emit(tmp_path, event_type="explode")


def test_invalid_risk_level_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="risk_level"):
        _emit(tmp_path, risk_level="extreme")


def test_invalid_result_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="result"):
        _emit(tmp_path, result="maybe")


def test_confidence_out_of_range_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="confidence_score"):
        _emit(tmp_path, confidence_score=101.0)
