"""Tests for two-log audit (execution + trace stub + decision)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_RUNTIME = REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from audit.two_log import TwoLogAudit  # noqa: E402
from workflows.run_log import append_run_log, read_last_entry  # noqa: E402


def test_record_workflow_run_writes_three_logs(tmp_path: Path):
    audit = TwoLogAudit(tmp_path)
    paths = audit.record_workflow_run(
        {
            "mode": "GO",
            "bead_id": "chromatic-harness-v2-chm",
            "decision": "plan_only",
            "confidence": {"confidence_score": 62.0, "cmp_decision": "replan"},
            "handoff": {"mission_id": "CHR-TEST"},
        }
    )
    assert audit.execution_path.is_file()
    assert audit.trace_path.is_file()
    assert audit.decision_path.is_file()
    assert "execution" in paths["execution"]

    exec_lines = [
        json.loads(ln)
        for ln in audit.execution_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith('{"_comment"')
    ]
    assert exec_lines[-1]["task_id"] == "chromatic-harness-v2-chm"
    assert exec_lines[-1]["idempotency_key"]

    trace_lines = [
        json.loads(ln)
        for ln in audit.trace_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and "_comment" not in ln
    ]
    assert trace_lines[-1]["attributes"]["workflow.mode"] == "GO"

    decision_lines = [
        json.loads(ln)
        for ln in audit.decision_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and "_comment" not in ln
    ]
    assert decision_lines[-1]["input_score"] == 62.0


def test_append_run_log_mirrors_two_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import workflows.run_log as run_log_mod

    wf_log = tmp_path / "docs" / "workflows" / "WORKFLOW_RUN_LOG.jsonl"
    monkeypatch.setattr(run_log_mod, "default_log_path", lambda _root: wf_log)

    append_run_log(
        tmp_path,
        {
            "mode": "GO AUDIT",
            "bead_id": "chromatic-harness-v2-test",
            "decision": "audit",
        },
    )
    assert wf_log.is_file()
    audit = TwoLogAudit(tmp_path)
    exec_lines = [
        json.loads(ln)
        for ln in audit.execution_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and "_comment" not in ln
    ]
    assert any(e["event_type"] == "workflow.go_audit" for e in exec_lines)

    last = read_last_entry(tmp_path)
    assert last is not None
    assert last["mode"] == "GO AUDIT"


def test_record_workflow_run_accepts_scalar_confidence(tmp_path: Path):
    audit = TwoLogAudit(tmp_path)
    audit.record_workflow_run(
        {
            "mode": "GO VERIFY",
            "bead_id": "chromatic-harness-v2-scalar",
            "decision": "execute",
            "confidence": 77,
            "handoff": {"mission_id": "CHR-SCALAR"},
        }
    )

    decision_lines = [
        json.loads(ln)
        for ln in audit.decision_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and "_comment" not in ln
    ]
    assert decision_lines
    assert decision_lines[-1]["input_score"] == 77
    assert decision_lines[-1]["band"] == "high"
