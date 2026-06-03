"""Tests for activity/log.py — emit_learning_outcome and related helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from activity.log import (
    ActivityLogResult,
    _event_to_mode,
    _should_enqueue_intake,
    emit_learning_outcome,
)


# ---------------------------------------------------------------------------
# emit_learning_outcome
# ---------------------------------------------------------------------------


class TestEmitLearningOutcome:
    def test_writes_applied_success_event(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        result = emit_learning_outcome(
            tmp_path,
            learning_name="my-pattern",
            outcome="applied_success",
        )

        assert result is True
        assert log.is_file()
        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert len(events) == 1
        e = events[0]
        assert e["event_type"] == "applied_success"
        assert e["learning_name"] == "my-pattern"
        assert "idempotency_key" in e
        assert "timestamp_utc" in e

    def test_writes_applied_failure_event(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        result = emit_learning_outcome(
            tmp_path,
            learning_name="another-pattern",
            outcome="applied_failure",
        )

        assert result is True
        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert events[0]["event_type"] == "applied_failure"

    def test_rejects_invalid_outcome(self, tmp_path: Path) -> None:
        result = emit_learning_outcome(tmp_path, learning_name="x", outcome="something_invalid")
        assert result is False

    def test_rejects_empty_learning_name(self, tmp_path: Path) -> None:
        result = emit_learning_outcome(tmp_path, learning_name="  ", outcome="applied_success")
        assert result is False

    def test_deduplicates_same_call(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        ts = "2026-01-01T00:00:00Z"
        emit_learning_outcome(tmp_path, learning_name="p1", outcome="applied_success", timestamp_utc=ts)
        second = emit_learning_outcome(tmp_path, learning_name="p1", outcome="applied_success", timestamp_utc=ts)

        assert second is False
        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert len(events) == 1

    def test_different_timestamps_are_not_duplicates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        emit_learning_outcome(
            tmp_path,
            learning_name="p1",
            outcome="applied_success",
            timestamp_utc="2026-01-01T00:00:00Z",
        )
        second = emit_learning_outcome(
            tmp_path,
            learning_name="p1",
            outcome="applied_success",
            timestamp_utc="2026-01-02T00:00:00Z",
        )

        assert second is True
        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert len(events) == 2

    def test_includes_rig_id_when_provided(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        emit_learning_outcome(tmp_path, learning_name="p2", outcome="applied_success", rig_id="rig-abc")

        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert events[0]["rig_id"] == "rig-abc"

    def test_omits_rig_id_when_not_provided(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        emit_learning_outcome(tmp_path, learning_name="p3", outcome="applied_success")

        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert "rig_id" not in events[0]

    def test_includes_error_category_on_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        emit_learning_outcome(
            tmp_path,
            learning_name="p4",
            outcome="applied_failure",
            error_category="merge_conflict",
        )

        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert events[0]["error_category"] == "merge_conflict"

    def test_omits_error_category_on_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        emit_learning_outcome(
            tmp_path,
            learning_name="p5",
            outcome="applied_success",
            error_category="merge_conflict",
        )

        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert "error_category" not in events[0]

    def test_creates_parent_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "deep" / "nested" / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        emit_learning_outcome(tmp_path, learning_name="p6", outcome="applied_success")

        assert log.is_file()

    def test_idempotency_key_is_16_hex_chars(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        emit_learning_outcome(tmp_path, learning_name="p7", outcome="applied_success")

        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        ikey = events[0]["idempotency_key"]
        assert len(ikey) == 16
        assert all(c in "0123456789abcdef" for c in ikey)

    def test_learning_path_field_is_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        emit_learning_outcome(tmp_path, learning_name="my-learning", outcome="applied_success")

        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert events[0]["learning_path"] == ".agents/learnings/my-learning.md"

    def test_notes_field_is_workflow_execution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        emit_learning_outcome(tmp_path, learning_name="p8", outcome="applied_success")

        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert events[0]["notes"] == "workflow_execution"

    def test_appends_multiple_distinct_events(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        log = tmp_path / "usage.jsonl"
        monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(log))

        for name in ("alpha", "beta", "gamma"):
            emit_learning_outcome(tmp_path, learning_name=name, outcome="applied_success")

        events = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
        assert len(events) == 3
        names = [e["learning_name"] for e in events]
        assert names == ["alpha", "beta", "gamma"]


# ---------------------------------------------------------------------------
# _event_to_mode
# ---------------------------------------------------------------------------


class TestEventToMode:
    def test_workflow_prefix_stripped(self) -> None:
        assert _event_to_mode("workflow.phase_complete") == "PHASE COMPLETE"

    def test_workflow_prefix_generic(self) -> None:
        assert _event_to_mode("workflow.start") == "START"

    def test_non_workflow_event(self) -> None:
        assert _event_to_mode("git.failed") == "GIT FAILED"

    def test_plain_event(self) -> None:
        assert _event_to_mode("test") == "TEST"

    def test_nested_dots_non_workflow(self) -> None:
        result = _event_to_mode("some.other.event")
        assert result == "SOME OTHER EVENT"


# ---------------------------------------------------------------------------
# _should_enqueue_intake
# ---------------------------------------------------------------------------


class TestShouldEnqueueIntake:
    def test_intake_on_failure_with_error_triggers(self) -> None:
        assert _should_enqueue_intake(lane="agent", error="something broke", intake_on_failure=True) is True

    def test_intake_on_failure_without_error_does_not_trigger(self) -> None:
        assert _should_enqueue_intake(lane="agent", error="", intake_on_failure=True) is False

    def test_human_lane_with_error_always_triggers(self) -> None:
        assert _should_enqueue_intake(lane="human", error="bad thing happened", intake_on_failure=False) is True

    def test_human_lane_without_error_does_not_trigger(self) -> None:
        assert _should_enqueue_intake(lane="human", error="", intake_on_failure=False) is False

    def test_agent_lane_no_error_no_intake(self) -> None:
        assert _should_enqueue_intake(lane="agent", error="", intake_on_failure=False) is False

    def test_whitespace_only_error_treated_as_no_error(self) -> None:
        assert _should_enqueue_intake(lane="agent", error="   ", intake_on_failure=True) is False


# ---------------------------------------------------------------------------
# ActivityLogResult
# ---------------------------------------------------------------------------


class TestActivityLogResult:
    def test_to_dict_contains_workflow_log_path(self) -> None:
        result = ActivityLogResult(workflow_log_path="/tmp/foo.jsonl")
        d = result.to_dict()
        assert d["workflow_log_path"] == "/tmp/foo.jsonl"

    def test_to_dict_defaults(self) -> None:
        result = ActivityLogResult(workflow_log_path="/p/q.jsonl")
        d = result.to_dict()
        assert d["intake_entry_id"] == ""
        assert d["intake_queued"] is False

    def test_to_dict_with_intake(self) -> None:
        result = ActivityLogResult(
            workflow_log_path="/p/q.jsonl",
            intake_entry_id="act-abc123",
            intake_queued=True,
        )
        d = result.to_dict()
        assert d["intake_entry_id"] == "act-abc123"
        assert d["intake_queued"] is True
