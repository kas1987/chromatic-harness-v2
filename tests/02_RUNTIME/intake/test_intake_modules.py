"""Tests for intake queue, bd_runner, auto_intake, inbox_adapter, and closure_feedback."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# ── intake.queue ──────────────────────────────────────────────────────────────

from intake.queue import (  # noqa: E402
    IntakeEntry,
    append_entry,
    default_queue_path,
    iter_queued,
    list_entries,
    list_queued,
    normalize_entry,
    record_status,
    validate_entry,
)


def _minimal(overrides: dict | None = None) -> dict:
    base = {
        "id": f"intake-{uuid.uuid4().hex[:8]}",
        "source": "manual",
        "kind": "goal",
        "status": "queued",
        "title": "Test task",
        "queued_at": "2026-01-01T00:00:00Z",
        "goal": "Do the thing",
    }
    base.update(overrides or {})
    return base


def test_validate_entry_valid() -> None:
    errors = validate_entry(_minimal())
    assert errors == []


def test_validate_entry_missing_required_field() -> None:
    data = _minimal()
    del data["title"]
    errors = validate_entry(data)
    assert any("title" in e for e in errors)


def test_validate_entry_invalid_source() -> None:
    errors = validate_entry(_minimal({"source": "bad_source"}))
    assert any("source" in e for e in errors)


def test_validate_entry_invalid_kind() -> None:
    errors = validate_entry(_minimal({"kind": "unknown_kind"}))
    assert any("kind" in e for e in errors)


def test_validate_entry_invalid_status() -> None:
    errors = validate_entry(_minimal({"status": "limbo"}))
    assert any("status" in e for e in errors)


def test_validate_entry_invalid_priority() -> None:
    errors = validate_entry(_minimal({"priority": "P9"}))
    assert any("priority" in e for e in errors)


def test_validate_entry_invalid_tier() -> None:
    errors = validate_entry(_minimal({"tier": 9}))
    assert any("tier" in e for e in errors)


def test_validate_entry_goal_kind_requires_goal() -> None:
    data = _minimal({"kind": "goal", "goal": ""})
    errors = validate_entry(data)
    assert any("goal" in e for e in errors)


def test_validate_entry_invalid_lane() -> None:
    errors = validate_entry(_minimal({"lane": "bad_lane"}))
    assert any("lane" in e for e in errors)


def test_validate_entry_valid_lanes() -> None:
    for lane in ("agent", "human", "review"):
        assert validate_entry(_minimal({"lane": lane})) == []


def test_normalize_entry_adds_defaults() -> None:
    data = {"id": "x", "source": "manual", "kind": "goal", "title": "T", "goal": "G"}
    out = normalize_entry(data)
    assert out["status"] == "queued"
    assert out["priority"] == "P2"
    assert out["type"] == "task"
    assert out["tier"] == 3


def test_normalize_entry_generates_id_when_missing() -> None:
    data = {"source": "manual", "kind": "goal", "title": "T", "goal": "G"}
    out = normalize_entry(data)
    assert out["id"].startswith("intake-")


def test_normalize_entry_goal_kind_sets_title_from_goal() -> None:
    data = {"source": "manual", "kind": "goal", "goal": "My long goal text"}
    out = normalize_entry(data)
    assert "My long goal text" in out["title"]


def test_append_entry_writes_to_file(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"
    entry = append_entry(_minimal(), path=q)
    assert q.is_file()
    assert isinstance(entry, IntakeEntry)


def test_append_entry_raises_on_invalid(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"
    with pytest.raises(ValueError):
        append_entry({"source": "bad_source", "kind": "goal"}, path=q)


def test_list_entries_empty_path(tmp_path: Path) -> None:
    assert list_entries(path=tmp_path / "nonexistent.jsonl") == []


def test_list_entries_returns_all(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"
    append_entry(_minimal({"id": "a"}), path=q)
    append_entry(_minimal({"id": "b"}), path=q)
    entries = list_entries(path=q)
    assert len(entries) == 2


def test_list_queued_dedupes_by_last_write(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"
    append_entry(_minimal({"id": "dup"}), path=q)
    # Overwrite with processed status
    append_entry(_minimal({"id": "dup", "status": "processed"}), path=q)
    queued = list_queued(path=q)
    assert all(e.id != "dup" for e in queued)


def test_list_queued_returns_only_queued(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"
    append_entry(_minimal({"id": "open1"}), path=q)
    append_entry(_minimal({"id": "done1", "status": "processed"}), path=q)
    queued = list_queued(path=q)
    ids = [e.id for e in queued]
    assert "open1" in ids
    assert "done1" not in ids


def test_iter_queued_yields_entries(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"
    append_entry(_minimal({"id": "it1"}), path=q)
    results = list(iter_queued(path=q))
    assert any(e.id == "it1" for e in results)


def test_record_status_appends_transition(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"
    entry = append_entry(_minimal({"id": "rs1"}), path=q)
    record_status(entry, "processed", path=q, bead_id="chromatic-harness-v2-xyz")
    entries = list_entries(path=q)
    last = entries[-1]
    assert last.status == "processed"
    assert last.bead_id == "chromatic-harness-v2-xyz"


def test_default_queue_path_uses_repo_root(tmp_path: Path) -> None:
    p = default_queue_path(tmp_path)
    assert "intake_queue.jsonl" in str(p)
    assert str(tmp_path) in str(p)


def test_intake_entry_from_dict_roundtrip() -> None:
    data = _minimal({"bead_id": "abc", "lane": "agent", "tier": 2})
    entry = IntakeEntry.from_dict(data)
    out = entry.to_dict()
    assert out["id"] == data["id"]
    assert out["lane"] == "agent"


def test_intake_entry_lane_from_context() -> None:
    data = _minimal({"context": {"lane": "human"}})
    if "lane" in data:
        del data["lane"]
    entry = IntakeEntry.from_dict(data)
    assert entry.lane == "human"


# ── intake.bd_runner ──────────────────────────────────────────────────────────

from intake.bd_runner import resolve_bd_argv  # noqa: E402


def test_resolve_bd_argv_returns_list() -> None:
    result = resolve_bd_argv()
    assert isinstance(result, list)
    assert len(result) >= 1


def test_resolve_bd_argv_last_element() -> None:
    result = resolve_bd_argv()
    assert result[-1].endswith("bd") or result[-1] == "bd"


# ── intake.auto_intake ────────────────────────────────────────────────────────

from intake.auto_intake import (  # noqa: E402
    DrainReport,
    ProcessResult,
    _existing_open_titles,
    _normalize_title,
    _should_skip,
    drain_queue,
    process_entry,
    simple_decompose,
)


def test_normalize_title_lowercases_and_strips() -> None:
    assert _normalize_title("  Hello World  ") == "hello world"


def test_normalize_title_removes_timestamp_token() -> None:
    raw = "Epic Title [20260530T091500Z] suffix"
    norm = _normalize_title(raw)
    assert "[20260530t091500z]" not in norm
    assert "epic title" in norm


def test_simple_decompose_single_line() -> None:
    tasks = simple_decompose("One atomic goal")
    assert len(tasks) == 1
    assert tasks[0]["title"] == "One atomic goal"


def test_simple_decompose_bullets() -> None:
    goal = "- First task\n- Second task\n- Third task\n"
    tasks = simple_decompose(goal)
    assert len(tasks) == 3
    assert "First task" in tasks[0]["title"]


def test_simple_decompose_numbered() -> None:
    goal = "1. First\n2. Second\n"
    tasks = simple_decompose(goal)
    assert len(tasks) == 2


def test_should_skip_example_prefix() -> None:
    class FakeEntry:
        id = "example-abc"
        title = "Example task"
        status = "queued"

    assert _should_skip(FakeEntry()) is True


def test_should_skip_agent_title() -> None:
    class FakeEntry:
        id = "intake-001"
        title = "[agent] auto task"
        status = "queued"

    assert _should_skip(FakeEntry()) is True


def test_should_not_skip_normal_entry() -> None:
    class FakeEntry:
        id = "intake-001"
        title = "Normal work item"
        status = "queued"

    assert _should_skip(FakeEntry()) is False


def test_should_skip_non_queued_status() -> None:
    class FakeEntry:
        id = "intake-001"
        title = "Some task"
        status = "processed"

    assert _should_skip(FakeEntry()) is True


def test_process_entry_bead_dispatch_dry_run(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"
    append_entry(
        {
            "id": "chromatic-harness-v2-abc1",
            "source": "bead_hook",
            "kind": "bead_dispatch",
            "status": "queued",
            "title": "Dispatch bead",
            "bead_id": "chromatic-harness-v2-abc1",
        },
        path=q,
    )
    entry = list_queued(path=q)[0]
    result = process_entry(entry, repo_root=tmp_path, queue_path=q, dry_run=True)
    assert result.status == "processed"
    assert result.bead_id == "chromatic-harness-v2-abc1"


def test_process_entry_skipped_example(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"
    append_entry(
        {
            "id": "example-skip",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "Skip",
            "goal": "nope",
        },
        path=q,
    )
    entry = list_queued(path=q)[0]
    result = process_entry(entry, repo_root=tmp_path, queue_path=q, dry_run=True)
    assert result.status == "skipped"


def test_process_entry_goal_via_mock_runner(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"

    def fake_runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
        if "create" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "Created chromatic-harness-v2-new1\n", "")
        return subprocess.CompletedProcess(cmd, 0, "Updated\n", "")

    append_entry(
        {
            "id": "goal-test",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "Grow the thing",
            "goal": "Do the thing and ship it",
        },
        path=q,
    )
    entry = list_queued(path=q)[0]
    result = process_entry(entry, repo_root=tmp_path, queue_path=q, runner=fake_runner)
    assert result.status == "processed"
    assert result.bead_id == "chromatic-harness-v2-new1"


def test_process_entry_create_failure(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"

    def fail_runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(cmd, 1, "", "bd error")

    append_entry(
        {
            "id": "fail-test",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "Will fail",
            "goal": "Fail",
        },
        path=q,
    )
    entry = list_queued(path=q)[0]
    result = process_entry(entry, repo_root=tmp_path, queue_path=q, runner=fail_runner)
    assert result.status == "failed"


def test_drain_queue_processes_all(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"

    def fake_runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
        if "list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        if "create" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "chromatic-harness-v2-dr1\n", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    for i in range(3):
        append_entry(
            {
                "id": f"drain-{i}",
                "source": "manual",
                "kind": "goal",
                "status": "queued",
                "title": f"Task {i}",
                "goal": f"Goal {i}",
            },
            path=q,
        )
    report = drain_queue(repo_root=tmp_path, queue_path=q, runner=fake_runner)
    assert report.processed + report.failed + report.skipped == 3


def test_drain_queue_skips_example(tmp_path: Path) -> None:
    q = tmp_path / "q.jsonl"

    def fake_runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
        if "list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    append_entry(
        {
            "id": "example-skip",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "Skip",
            "goal": "nope",
        },
        path=q,
    )
    report = drain_queue(repo_root=tmp_path, queue_path=q, runner=fake_runner)
    assert report.skipped == 1


def test_process_result_to_dict() -> None:
    r = ProcessResult("id1", "goal", "processed", bead_id="b1", message="ok")
    d = r.to_dict()
    assert d["entry_id"] == "id1"
    assert d["bead_id"] == "b1"


def test_drain_report_to_dict() -> None:
    r = DrainReport(processed=2, failed=1, skipped=0)
    d = r.to_dict()
    assert d["processed"] == 2
    assert d["failed"] == 1


def test_existing_open_titles_empty_on_bd_failure(tmp_path: Path) -> None:
    def fail_runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(cmd, 1, "", "error")

    titles = _existing_open_titles(cwd=tmp_path, runner=fail_runner)
    assert titles == set()


def test_existing_open_titles_parses_json(tmp_path: Path) -> None:
    payload = json.dumps([{"title": "My Open Task"}])

    def ok_runner(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(cmd, 0, payload, "")

    titles = _existing_open_titles(cwd=tmp_path, runner=ok_runner)
    assert "my open task" in titles


# ── intake.closure_feedback ───────────────────────────────────────────────────

from intake.closure_feedback import enqueue_session_follow_ups  # noqa: E402


def test_enqueue_session_follow_ups_basic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import intake.queue as qmod

    q = tmp_path / "q.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    ids = enqueue_session_follow_ups(["Fix the auth bug", "Write test coverage"], mission_id="M-99")
    assert len(ids) == 2
    assert all(i.startswith("fu-M-99") for i in ids)


def test_enqueue_skips_empty_goals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import intake.queue as qmod

    q = tmp_path / "q.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    ids = enqueue_session_follow_ups(["", "   ", "Real goal"], mission_id="M1")
    assert len(ids) == 1


def test_enqueue_skips_separator_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import intake.queue as qmod

    q = tmp_path / "q.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    ids = enqueue_session_follow_ups(["---", "—", "Real work"], mission_id="M2")
    assert len(ids) == 1


def test_enqueue_skips_see_git_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import intake.queue as qmod

    q = tmp_path / "q.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    ids = enqueue_session_follow_ups(["(see git log)", "Real task"])
    assert len(ids) == 1


def test_enqueue_context_includes_parent_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import intake.queue as qmod

    q = tmp_path / "q.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    enqueue_session_follow_ups(["Do work"], mission_id="MISSION-X")
    entries = list_entries(path=q)
    assert entries[-1].context.get("parent_mission") == "MISSION-X"


def test_enqueue_follow_ups_no_mission_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import intake.queue as qmod

    q = tmp_path / "q.jsonl"
    monkeypatch.setattr(qmod, "default_queue_path", lambda repo_root=None: q)

    ids = enqueue_session_follow_ups(["Task A"])
    assert len(ids) == 1
    assert ids[0].startswith("fu-session-")


# ── intake.inbox_adapter ──────────────────────────────────────────────────────

from intake.inbox_adapter import (  # noqa: E402
    InboxPollReport,
    _normalize_priority,
    resolve_inbox_db,
    resolve_inbox_root,
)


def test_normalize_priority_valid() -> None:
    assert _normalize_priority("P0") == "P0"
    assert _normalize_priority("P3") == "P3"


def test_normalize_priority_digit_string() -> None:
    assert _normalize_priority("0") == "P0"
    assert _normalize_priority("2") == "P2"


def test_normalize_priority_unknown_defaults_p2() -> None:
    assert _normalize_priority("X99") == "P2"
    assert _normalize_priority(None) == "P2"


def test_resolve_inbox_root_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHROMATIC_INBOX_ROOT", "")
    # With no valid db file present, should return None
    result = resolve_inbox_root()
    assert result is None


def test_resolve_inbox_db_explicit_nonexistent(tmp_path: Path) -> None:
    fake = tmp_path / "nope.sqlite"
    assert resolve_inbox_db(fake) is None


def test_inbox_poll_report_to_dict() -> None:
    r = InboxPollReport(fetched=5, appended=3, skipped=2)
    d = r.to_dict()
    assert d["fetched"] == 5
    assert d["appended"] == 3
    assert d["skipped"] == 2
    assert isinstance(d["errors"], list)
