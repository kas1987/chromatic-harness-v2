"""Tests for unified activity logging and dual-backlog lanes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from activity.lanes import apply_lane_to_bead_fields  # noqa: E402
from activity.log import emit_learning_outcome, log_activity  # noqa: E402
from audit.two_log import TwoLogAudit  # noqa: E402
from intake.auto_intake import drain_queue  # noqa: E402
from intake.queue import list_queued  # noqa: E402
import workflows.run_log as run_log_mod  # noqa: E402


def test_apply_lane_prefix_and_description():
    title, desc = apply_lane_to_bead_fields("Fix tests", "Details here", lane="human")
    assert title.startswith("[human]")
    assert desc.startswith("lane: human")


def test_log_activity_writes_workflow_and_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    wf = tmp_path / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"
    monkeypatch.setattr(run_log_mod, "runtime_log_path", lambda _r: wf)
    monkeypatch.setattr(run_log_mod, "default_log_path", lambda _r: wf)

    result = log_activity(
        tmp_path,
        event_type="phase.complete",
        bead_id="chromatic-harness-v2-test",
        lane="agent",
        decision="ok",
        summary="smoke phase done",
    )
    assert wf.is_file()
    assert result.intake_queued is False

    audit = TwoLogAudit(tmp_path)
    lines = [
        json.loads(ln)
        for ln in audit.execution_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and "_comment" not in ln
    ]
    assert any(e.get("event_type") == "activity.phase.complete" for e in lines)


def test_log_activity_enqueues_human_intake_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    wf = tmp_path / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"
    monkeypatch.setattr(run_log_mod, "runtime_log_path", lambda _r: wf)
    monkeypatch.setattr(run_log_mod, "default_log_path", lambda _r: wf)
    queue = tmp_path / "07_LOGS_AND_AUDIT" / "intake_queue.jsonl"

    result = log_activity(
        tmp_path,
        event_type="git.failed",
        lane="human",
        error="cannot pull with rebase: unstaged changes",
        summary="push blocked",
        intake_on_failure=True,
    )
    assert result.intake_queued
    queued = list_queued(path=queue, repo_root=tmp_path)
    assert any(e.lane == "human" for e in queued)


def test_auto_intake_applies_lane_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    queue = tmp_path / "07_LOGS_AND_AUDIT" / "intake_queue.jsonl"
    queue.parent.mkdir(parents=True, exist_ok=True)

    from intake.queue import append_entry  # noqa: E402

    append_entry(
        {
            "id": "lane-follow-1",
            "source": "workflow",
            "kind": "follow_up",
            "status": "queued",
            "title": "Agent subtask",
            "goal": "Do scoped fix",
            "lane": "agent",
            "queued_at": "2026-05-30T12:00:00Z",
        },
        path=queue,
        repo_root=tmp_path,
    )

    created_titles: list[str] = []

    def fake_runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if "create" in cmd:
            title = cmd[2] if len(cmd) > 2 else ""
            created_titles.append(title)
            return subprocess.CompletedProcess(cmd, 0, "chromatic-harness-v2-fake01\n", "")
        return subprocess.CompletedProcess(cmd, 0, "ok\n", "")

    import subprocess  # noqa: E402

    report = drain_queue(
        repo_root=tmp_path,
        queue_path=queue,
        dry_run=False,
        claim=False,
        runner=fake_runner,
    )
    assert report.processed == 1
    assert created_titles and created_titles[0].startswith("[agent]")


def test_emit_learning_outcome_writes_applied_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    usage_log = tmp_path / ".agents" / "metrics" / "learning_usage.jsonl"
    monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(usage_log))

    emitted = emit_learning_outcome(
        tmp_path,
        learning_name="my-learning",
        outcome="applied_success",
        rig_id="chromatic-harness-v2-test",
    )
    assert emitted is True
    assert usage_log.is_file()
    events = [json.loads(ln) for ln in usage_log.read_text().splitlines() if ln.strip()]
    assert len(events) == 1
    assert events[0]["event_type"] == "applied_success"
    assert events[0]["learning_name"] == "my-learning"
    assert events[0]["rig_id"] == "chromatic-harness-v2-test"
    assert "idempotency_key" in events[0]


def test_emit_learning_outcome_writes_applied_failure_with_category(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    usage_log = tmp_path / ".agents" / "metrics" / "learning_usage.jsonl"
    monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(usage_log))

    emit_learning_outcome(
        tmp_path,
        learning_name="my-learning",
        outcome="applied_failure",
        error_category="merge_conflict",
    )
    events = [json.loads(ln) for ln in usage_log.read_text().splitlines() if ln.strip()]
    assert events[0]["event_type"] == "applied_failure"
    assert events[0]["error_category"] == "merge_conflict"


def test_emit_learning_outcome_deduplicates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    usage_log = tmp_path / ".agents" / "metrics" / "learning_usage.jsonl"
    monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(usage_log))

    ts = "2026-05-30T00:00:00Z"
    emit_learning_outcome(
        tmp_path,
        learning_name="dup-learning",
        outcome="applied_success",
        timestamp_utc=ts,
    )
    second = emit_learning_outcome(
        tmp_path,
        learning_name="dup-learning",
        outcome="applied_success",
        timestamp_utc=ts,
    )
    assert second is False
    events = [json.loads(ln) for ln in usage_log.read_text().splitlines() if ln.strip()]
    assert len(events) == 1


def test_emit_learning_outcome_rejects_invalid_outcome(tmp_path: Path) -> None:
    result = emit_learning_outcome(tmp_path, learning_name="x", outcome="unknown")
    assert result is False


def test_log_activity_emits_applied_success_when_learning_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wf = tmp_path / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"
    monkeypatch.setattr(run_log_mod, "runtime_log_path", lambda _r: wf)
    monkeypatch.setattr(run_log_mod, "default_log_path", lambda _r: wf)
    usage_log = tmp_path / ".agents" / "metrics" / "learning_usage.jsonl"
    monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(usage_log))

    log_activity(
        tmp_path,
        event_type="phase.complete",
        bead_id="chromatic-harness-v2-t1",
        applied_learning="live-query-first-pattern",
    )
    assert usage_log.is_file()
    events = [json.loads(ln) for ln in usage_log.read_text().splitlines() if ln.strip()]
    assert any(
        e["event_type"] == "applied_success" and e["learning_name"] == "live-query-first-pattern" for e in events
    )


def test_log_activity_emits_applied_failure_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wf = tmp_path / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"
    monkeypatch.setattr(run_log_mod, "runtime_log_path", lambda _r: wf)
    monkeypatch.setattr(run_log_mod, "default_log_path", lambda _r: wf)
    usage_log = tmp_path / ".agents" / "metrics" / "learning_usage.jsonl"
    monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(usage_log))

    log_activity(
        tmp_path,
        event_type="git.failed",
        bead_id="chromatic-harness-v2-t2",
        error="push rejected",
        applied_learning="safe-git-workflow-pattern",
        error_category="push_rejected",
    )
    events = [json.loads(ln) for ln in usage_log.read_text().splitlines() if ln.strip()]
    assert any(
        e["event_type"] == "applied_failure"
        and e["learning_name"] == "safe-git-workflow-pattern"
        and e.get("error_category") == "push_rejected"
        for e in events
    )


def test_log_activity_no_learning_emission_when_not_provided(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wf = tmp_path / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"
    monkeypatch.setattr(run_log_mod, "runtime_log_path", lambda _r: wf)
    monkeypatch.setattr(run_log_mod, "default_log_path", lambda _r: wf)
    usage_log = tmp_path / ".agents" / "metrics" / "learning_usage.jsonl"
    monkeypatch.setenv("CHROMATIC_LEARNING_USAGE_LOG", str(usage_log))

    log_activity(tmp_path, event_type="phase.start", summary="starting")
    assert not usage_log.is_file()
