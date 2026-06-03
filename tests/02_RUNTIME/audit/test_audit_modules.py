"""Tests for audit.two_log and audit.session_events modules."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from audit.two_log import (  # noqa: E402
    TwoLogAudit,
    _append_jsonl,
    _hash_payload,
    _repo_root,
    record_workflow_event,
)


# ── _repo_root ────────────────────────────────────────────────────────────────


def test_repo_root_explicit(tmp_path: Path) -> None:
    assert _repo_root(tmp_path) == tmp_path


def test_repo_root_finds_git(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    result = _repo_root(None)
    # Just confirm it returns a Path (can't control where it resolves from __file__)
    assert isinstance(result, Path)


def test_repo_root_explicit_overrides_search(tmp_path: Path) -> None:
    result = _repo_root(tmp_path)
    assert result == tmp_path


# ── _hash_payload ─────────────────────────────────────────────────────────────


def test_hash_payload_deterministic() -> None:
    a = _hash_payload({"key": "value", "n": 42})
    b = _hash_payload({"key": "value", "n": 42})
    assert a == b


def test_hash_payload_length() -> None:
    result = _hash_payload({"x": 1})
    assert len(result) == 16


def test_hash_payload_different_inputs_different_hashes() -> None:
    a = _hash_payload({"k": "v1"})
    b = _hash_payload({"k": "v2"})
    assert a != b


def test_hash_payload_sorts_keys() -> None:
    a = _hash_payload({"b": 2, "a": 1})
    b = _hash_payload({"a": 1, "b": 2})
    assert a == b


# ── _append_jsonl ─────────────────────────────────────────────────────────────


def test_append_jsonl_creates_file(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "test.jsonl"
    _append_jsonl(path, {"hello": "world"})
    assert path.is_file()
    data = json.loads(path.read_text())
    assert data["hello"] == "world"


def test_append_jsonl_multiple_lines(tmp_path: Path) -> None:
    path = tmp_path / "out.jsonl"
    _append_jsonl(path, {"n": 1})
    _append_jsonl(path, {"n": 2})
    lines = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2
    assert lines[0]["n"] == 1
    assert lines[1]["n"] == 2


# ── TwoLogAudit ───────────────────────────────────────────────────────────────


def test_two_log_audit_paths(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    assert "execution" in str(audit.execution_path)
    assert "traces" in str(audit.trace_path)
    assert "decisions" in str(audit.decision_path)


def test_append_execution_writes_ts(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.append_execution({"event_type": "test.event"})
    lines = [json.loads(ln) for ln in audit.execution_path.read_text().splitlines() if ln.strip()]
    assert lines[-1]["event_type"] == "test.event"
    assert "ts" in lines[-1]


def test_append_trace_span_adds_trace_id(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.append_trace_span({"name": "my.span", "kind": "INTERNAL", "status": "OK"})
    lines = [json.loads(ln) for ln in audit.trace_path.read_text().splitlines() if ln.strip()]
    assert lines[-1]["name"] == "my.span"
    assert "trace_id" in lines[-1]
    assert "span_id" in lines[-1]
    assert "timestamp" in lines[-1]


def test_append_decision_writes_ts(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.append_decision({"gate": "confidence", "action": "plan_only"})
    lines = [json.loads(ln) for ln in audit.decision_path.read_text().splitlines() if ln.strip()]
    assert lines[-1]["gate"] == "confidence"
    assert "ts" in lines[-1]


def test_record_workflow_run_writes_all_three(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    paths = audit.record_workflow_run(
        {
            "mode": "GO",
            "bead_id": "chromatic-harness-v2-abc",
            "decision": "execute",
            "confidence": {"confidence_score": 80.0, "cmp_decision": "execute"},
            "handoff": {"mission_id": "M-001"},
        }
    )
    assert audit.execution_path.is_file()
    assert audit.trace_path.is_file()
    assert audit.decision_path.is_file()
    assert "execution" in paths["execution"]
    assert "trace" in paths["trace"]
    assert "decision" in paths["decision"]


def test_record_workflow_run_event_type_activity_prefix_passthrough(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.record_workflow_run({"mode": "MY_MODE", "event_type": "activity.session.end", "decision": ""})
    lines = [json.loads(ln) for ln in audit.execution_path.read_text().splitlines() if ln.strip()]
    assert lines[-1]["event_type"] == "activity.session.end"


def test_record_workflow_run_workflow_prefix_passthrough(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.record_workflow_run({"mode": "GO_VERIFY", "event_type": "workflow.go_verify", "decision": ""})
    lines = [json.loads(ln) for ln in audit.execution_path.read_text().splitlines() if ln.strip()]
    assert lines[-1]["event_type"] == "workflow.go_verify"


def test_record_workflow_run_bare_event_type_gets_prefix(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.record_workflow_run({"mode": "GO_VERIFY", "event_type": "my_raw", "decision": ""})
    lines = [json.loads(ln) for ln in audit.execution_path.read_text().splitlines() if ln.strip()]
    assert lines[-1]["event_type"].startswith("activity.")


def test_record_workflow_run_high_confidence_band(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.record_workflow_run({"mode": "GO", "bead_id": "b1", "confidence": 90, "decision": "execute"})
    lines = [json.loads(ln) for ln in audit.decision_path.read_text().splitlines() if ln.strip()]
    assert lines[-1]["band"] == "high"


def test_record_workflow_run_medium_band(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.record_workflow_run({"mode": "GO", "bead_id": "b1", "confidence": 60, "decision": "plan_only"})
    lines = [json.loads(ln) for ln in audit.decision_path.read_text().splitlines() if ln.strip()]
    assert lines[-1]["band"] == "medium"


def test_record_workflow_run_low_band(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.record_workflow_run({"mode": "GO", "bead_id": "b1", "confidence": 10, "decision": "pause"})
    lines = [json.loads(ln) for ln in audit.decision_path.read_text().splitlines() if ln.strip()]
    assert lines[-1]["band"] == "low"


def test_record_workflow_run_no_decision_skips_decision_log(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.record_workflow_run({"mode": "IDLE", "decision": "", "confidence": None})
    assert not audit.decision_path.is_file()


def test_record_workflow_run_side_effect_receipt(tmp_path: Path) -> None:
    audit = TwoLogAudit(tmp_path)
    audit.record_workflow_run({"mode": "GO", "decision": "execute"})
    lines = [json.loads(ln) for ln in audit.execution_path.read_text().splitlines() if ln.strip()]
    assert lines[-1]["side_effect_receipt"] is True


def test_record_workflow_event_convenience(tmp_path: Path) -> None:
    paths = record_workflow_event(
        tmp_path,
        {"mode": "GO", "bead_id": "chromatic-harness-v2-x1", "decision": "shipped"},
    )
    assert "execution" in paths


# ── session_events ────────────────────────────────────────────────────────────


def _load_session_events():
    return importlib.import_module("audit.session_events")


@pytest.fixture()
def repo_with_sot(tmp_path: Path) -> Path:
    (tmp_path / "00_SOURCE_OF_TRUTH").mkdir()
    return tmp_path


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def test_emit_session_boot_ok(repo_with_sot: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHROMATIC_SESSION_ID", "sess-boot-test")
    se = _load_session_events()
    result = se.emit_session_boot(repo_with_sot, cold_start=True)
    assert result["ok"] is True
    assert result["session_id"] == "sess-boot-test"


def test_emit_session_boot_writes_execution_log(repo_with_sot: Path) -> None:
    se = _load_session_events()
    se.emit_session_boot(repo_with_sot, cold_start=False)
    exec_log = repo_with_sot / "07_LOGS_AND_AUDIT" / "execution" / "execution.jsonl"
    assert exec_log.is_file()
    rows = _read_jsonl(exec_log)
    assert rows[-1]["event_type"] == "session.boot"
    assert rows[-1]["cold_start"] is False


def test_emit_session_boot_cold_start_true(repo_with_sot: Path) -> None:
    se = _load_session_events()
    se.emit_session_boot(repo_with_sot, cold_start=True)
    exec_log = repo_with_sot / "07_LOGS_AND_AUDIT" / "execution" / "execution.jsonl"
    rows = _read_jsonl(exec_log)
    assert rows[-1]["cold_start"] is True


def test_emit_session_boot_writes_trace(repo_with_sot: Path) -> None:
    se = _load_session_events()
    se.emit_session_boot(repo_with_sot)
    trace_log = repo_with_sot / "07_LOGS_AND_AUDIT" / "traces" / "traces.jsonl"
    assert trace_log.is_file()
    spans = _read_jsonl(trace_log)
    assert spans[-1]["name"] == "session.boot"


def test_emit_session_boot_includes_boot_ts(repo_with_sot: Path) -> None:
    se = _load_session_events()
    se.emit_session_boot(repo_with_sot)
    exec_log = repo_with_sot / "07_LOGS_AND_AUDIT" / "execution" / "execution.jsonl"
    rows = _read_jsonl(exec_log)
    assert "boot_ts" in rows[-1]


def test_emit_session_end_ok(repo_with_sot: Path) -> None:
    se = _load_session_events()
    result = se.emit_session_end(repo_with_sot, invoked_by="closeout")
    assert result["ok"] is True


def test_emit_session_end_writes_event_type(repo_with_sot: Path) -> None:
    se = _load_session_events()
    se.emit_session_end(repo_with_sot)
    exec_log = repo_with_sot / "07_LOGS_AND_AUDIT" / "execution" / "execution.jsonl"
    rows = _read_jsonl(exec_log)
    assert rows[-1]["event_type"] == "session.end"


def test_emit_session_event_extra_fields(repo_with_sot: Path) -> None:
    se = _load_session_events()
    se.emit_session_event("session.boot", repo_with_sot, extra={"custom_key": "custom_val"})
    exec_log = repo_with_sot / "07_LOGS_AND_AUDIT" / "execution" / "execution.jsonl"
    rows = _read_jsonl(exec_log)
    assert rows[-1]["custom_key"] == "custom_val"


def test_emit_session_boot_fail_open(repo_with_sot: Path) -> None:
    se = _load_session_events()

    class BrokenAudit:
        def append_execution(self, *_a, **_k):
            raise RuntimeError("disk full")

    result = se.emit_session_boot(repo_with_sot, audit=BrokenAudit())
    assert result["ok"] is False
    assert "disk full" in result["error"]


def test_session_id_from_env(repo_with_sot: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_SESSION_ID", "claude-123")
    monkeypatch.delenv("CHROMATIC_SESSION_ID", raising=False)
    se = _load_session_events()
    result = se.emit_session_boot(repo_with_sot)
    assert result["session_id"] == "claude-123"


def test_session_id_synthesized_when_no_env(repo_with_sot: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.delenv("CHROMATIC_SESSION_ID", raising=False)
    se = _load_session_events()
    result = se.emit_session_boot(repo_with_sot)
    assert result["ok"] is True
    assert len(result["session_id"]) == 32  # uuid4().hex length


def test_emit_session_event_invoked_by_default(repo_with_sot: Path) -> None:
    se = _load_session_events()
    result = se.emit_session_event("session.boot", repo_with_sot)
    exec_log = repo_with_sot / "07_LOGS_AND_AUDIT" / "execution" / "execution.jsonl"
    rows = _read_jsonl(exec_log)
    assert rows[-1]["invoked_by"] == "session_start"
