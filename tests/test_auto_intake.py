"""Tests for auto_intake queue drain."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from intake.auto_intake import (
    _normalize_title,
    _should_skip,
    drain_queue,
    process_entry,
    simple_decompose,
)
from intake.queue import append_entry, list_queued

REPO = Path(__file__).resolve().parents[1]


def test_simple_decompose_bullets():
    goal = "- First task\n- Second task\n"
    tasks = simple_decompose(goal)
    assert len(tasks) == 2
    assert "First" in tasks[0]["title"]


def test_simple_decompose_single():
    tasks = simple_decompose("One atomic goal")
    assert len(tasks) == 1


def test_process_bead_dispatch_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import intake.queue as qmod

    q = tmp_path / "intake_queue.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    append_entry(
        {
            "id": "chromatic-harness-v2-test1",
            "source": "bead_hook",
            "kind": "bead_dispatch",
            "status": "queued",
            "title": "Test dispatch",
            "bead_id": "chromatic-harness-v2-test1",
        },
        path=q,
    )
    entry = list_queued(path=q)[0]
    result = process_entry(entry, repo_root=tmp_path, queue_path=q, dry_run=True)
    assert result.status == "processed"
    assert result.bead_id == "chromatic-harness-v2-test1"


def test_process_goal_creates_via_mock_bd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import intake.queue as qmod

    q = tmp_path / "intake_queue.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    calls: list[list[str]] = []

    def fake_runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if "create" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, "✓ Created issue: chromatic-harness-v2-abc1\n", ""
            )
        return subprocess.CompletedProcess(cmd, 0, "✓ Updated issue\n", "")

    append_entry(
        {
            "id": "goal-test-1",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "Ship intake",
            "goal": "Ship intake loop",
            "priority": "P1",
        },
        path=q,
    )
    entry = list_queued(path=q)[0]
    result = process_entry(
        entry,
        repo_root=tmp_path,
        queue_path=q,
        runner=fake_runner,
    )
    assert result.status == "processed"
    assert result.bead_id == "chromatic-harness-v2-abc1"
    assert any("create" in c for c in calls)


def test_drain_skips_example_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import intake.queue as qmod

    q = tmp_path / "intake_queue.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    append_entry(
        {
            "id": "example-skip-me",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "Skip",
            "goal": "nope",
        },
        path=q,
    )
    report = drain_queue(repo_root=tmp_path, queue_path=q, dry_run=True)
    assert report.skipped == 1
    assert report.processed == 0


def test_should_skip_agent_title_prefix():
    class Entry:
        id = "intake-123"
        title = "[agent] Run new_session_bootstrap.py"
        status = "queued"

    assert _should_skip(Entry()) is True


def test_should_not_skip_normal_queued_title():
    class Entry:
        id = "intake-123"
        title = "Real follow-up work"
        status = "queued"

    assert _should_skip(Entry()) is False


def test_validate_intake_loop_script():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "validate_intake_loop.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Intake close-loop validation OK" in proc.stdout


def test_process_epic_adds_timestamp_and_telemetry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import intake.queue as qmod

    q = tmp_path / "intake_queue.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    calls: list[list[str]] = []

    def fake_runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if "create" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, "✓ Created issue: chromatic-harness-v2-epic1\n", ""
            )
        return subprocess.CompletedProcess(cmd, 0, "✓ Updated issue\n", "")

    append_entry(
        {
            "id": "epic-test-1",
            "source": "manual",
            "kind": "follow_up",
            "status": "queued",
            "title": "Epic telemetry smoke",
            "goal": "Ensure intake-created epics have machine-friendly metadata.",
            "type": "epic",
            "priority": "P1",
        },
        path=q,
    )
    entry = list_queued(path=q)[0]
    result = process_entry(
        entry,
        repo_root=tmp_path,
        queue_path=q,
        runner=fake_runner,
    )
    assert result.status == "processed"

    create_cmd = next(c for c in calls if "create" in c)
    create_idx = create_cmd.index("create")
    title = create_cmd[create_idx + 1]
    assert " [" in title and title.endswith("]")

    desc = create_cmd[create_cmd.index("--description") + 1]
    assert "telemetry_key: EPIC-AUTO-" in desc
    assert "timestamp_utc:" in desc


def test_normalize_title_ignores_timestamp_token():
    raw = "EPIC-SWOT NEXT [20260530T091500Z]: Post-Closeout SWOT Seed"
    norm = _normalize_title(raw)
    assert "[20260530t091500z]" not in norm
    assert "epic-swot next" in norm
