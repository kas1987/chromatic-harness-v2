"""Unit tests for scripts/validate_intake_loop.py.

Tests individual check functions by mocking their dependencies (run_safe,
intake queue, auto_intake drain). Uses tmp directories — no live bd / DB.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_REPO = Path(__file__).resolve().parents[2]
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

_spec = importlib.util.spec_from_file_location("validate_intake_loop", _REPO / "scripts" / "validate_intake_loop.py")
vil = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vil)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _ok_proc(stdout="", stderr=""):
    r = MagicMock()
    r.returncode = 0
    r.stdout = stdout
    r.stderr = stderr
    return r


def _fail_proc(stdout="", stderr="error"):
    r = MagicMock()
    r.returncode = 1
    r.stdout = stdout
    r.stderr = stderr
    return r


# ---------------------------------------------------------------------------
# check_schema_and_decompose
# ---------------------------------------------------------------------------


def test_check_schema_and_decompose_passes():
    errors = vil.check_schema_and_decompose(verbose=False)
    assert errors == []


def test_check_schema_and_decompose_verbose_no_errors():
    errors = vil.check_schema_and_decompose(verbose=True)
    assert errors == []


# ---------------------------------------------------------------------------
# check_two_log_audit
# ---------------------------------------------------------------------------


def test_check_two_log_audit_passes_when_all_present(monkeypatch, tmp_path):
    # Create the required files under tmp_path
    for rel in (
        "07_LOGS_AND_AUDIT/execution/execution.jsonl",
        "07_LOGS_AND_AUDIT/traces/traces.jsonl",
        "07_LOGS_AND_AUDIT/decisions/decision_log.jsonl",
        "docs/workflows/TWO_LOG_AUDIT.md",
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")

    monkeypatch.setattr(vil, "REPO", tmp_path)
    errors = vil.check_two_log_audit(verbose=False)
    assert errors == []


def test_check_two_log_audit_fails_for_missing_artifact(monkeypatch, tmp_path):
    # Only create 3 of the 4 required files
    for rel in (
        "07_LOGS_AND_AUDIT/execution/execution.jsonl",
        "07_LOGS_AND_AUDIT/traces/traces.jsonl",
        "07_LOGS_AND_AUDIT/decisions/decision_log.jsonl",
        # TWO_LOG_AUDIT.md deliberately absent
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")

    monkeypatch.setattr(vil, "REPO", tmp_path)
    errors = vil.check_two_log_audit(verbose=False)
    assert any("TWO_LOG_AUDIT.md" in e for e in errors)


# ---------------------------------------------------------------------------
# check_workflow_go_audit
# ---------------------------------------------------------------------------


def test_check_workflow_go_audit_passes_on_valid_json(monkeypatch):
    monkeypatch.setattr(
        vil,
        "run_safe",
        lambda cmd, cwd=None, timeout=90: _ok_proc(stdout=json.dumps({"mode": "GO AUDIT", "bead_id": "b1"})),
    )
    errors = vil.check_workflow_go_audit(verbose=False)
    assert errors == []


def test_check_workflow_go_audit_fails_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        vil,
        "run_safe",
        lambda cmd, cwd=None, timeout=90: _fail_proc(stderr="workflow_go failed"),
    )
    errors = vil.check_workflow_go_audit(verbose=False)
    assert len(errors) == 1
    assert "GO AUDIT failed" in errors[0]


def test_check_workflow_go_audit_fails_on_bad_json(monkeypatch):
    monkeypatch.setattr(
        vil,
        "run_safe",
        lambda cmd, cwd=None, timeout=90: _ok_proc(stdout="NOT JSON"),
    )
    errors = vil.check_workflow_go_audit(verbose=False)
    assert any("invalid JSON" in e for e in errors)


def test_check_workflow_go_audit_fails_on_missing_mode(monkeypatch):
    monkeypatch.setattr(
        vil,
        "run_safe",
        lambda cmd, cwd=None, timeout=90: _ok_proc(stdout=json.dumps({"bead_id": "b1"})),
    )
    errors = vil.check_workflow_go_audit(verbose=False)
    assert any("missing mode" in e for e in errors)


# ---------------------------------------------------------------------------
# check_workflow_go_verify
# ---------------------------------------------------------------------------


def test_check_workflow_go_verify_passes_on_git_pipeline(monkeypatch):
    monkeypatch.setattr(
        vil,
        "run_safe",
        lambda cmd, cwd=None, timeout=90: _ok_proc(stdout=json.dumps({"git_pipeline": "ok"})),
    )
    errors = vil.check_workflow_go_verify(verbose=False)
    assert errors == []


def test_check_workflow_go_verify_tolerates_no_prior_run(monkeypatch):
    monkeypatch.setattr(
        vil,
        "run_safe",
        lambda cmd, cwd=None, timeout=90: _fail_proc(stdout="no prior workflow run found"),
    )
    errors = vil.check_workflow_go_verify(verbose=False)
    assert errors == []


def test_check_workflow_go_verify_fails_hard_error(monkeypatch):
    monkeypatch.setattr(
        vil,
        "run_safe",
        lambda cmd, cwd=None, timeout=90: _fail_proc(stderr="fatal error", stdout=""),
    )
    errors = vil.check_workflow_go_verify(verbose=False)
    assert len(errors) == 1
    assert "GO VERIFY failed" in errors[0]


# ---------------------------------------------------------------------------
# check_auto_intake_cli
# ---------------------------------------------------------------------------


def test_check_auto_intake_cli_passes_on_valid_output(monkeypatch):
    monkeypatch.setattr(
        vil,
        "run_safe",
        lambda cmd, cwd=None, timeout=60: _ok_proc(stdout=json.dumps({"processed": 0, "errors": []})),
    )
    errors = vil.check_auto_intake_cli(verbose=False)
    assert errors == []


def test_check_auto_intake_cli_fails_on_nonzero(monkeypatch):
    monkeypatch.setattr(
        vil,
        "run_safe",
        lambda cmd, cwd=None, timeout=60: _fail_proc(stderr="auto_intake died"),
    )
    errors = vil.check_auto_intake_cli(verbose=False)
    assert len(errors) == 1
    assert "auto_intake CLI failed" in errors[0]


def test_check_auto_intake_cli_fails_on_missing_processed(monkeypatch):
    monkeypatch.setattr(
        vil,
        "run_safe",
        lambda cmd, cwd=None, timeout=60: _ok_proc(stdout=json.dumps({"other_key": 1})),
    )
    errors = vil.check_auto_intake_cli(verbose=False)
    assert any("processed" in e for e in errors)


# ---------------------------------------------------------------------------
# check_drain_dry_run
# ---------------------------------------------------------------------------


def _make_drain_report(processed: int = 2):
    """Build a minimal DrainReport-like object with .processed and .to_dict()."""
    r = MagicMock()
    r.processed = processed
    r.to_dict.return_value = {"processed": processed, "errors": []}
    return r


def test_check_drain_dry_run_appends_and_drains(tmp_path, monkeypatch):
    q = tmp_path / "intake_queue.jsonl"
    # Patch drain_queue so no subprocess / bd call is made
    monkeypatch.setattr(vil, "drain_queue", lambda **kw: _make_drain_report(processed=2))
    errors = vil.check_drain_dry_run(q, verbose=False)
    assert errors == []
    # Queue file should have been written (by append_entry)
    assert q.is_file()


def test_check_drain_dry_run_queue_has_two_entries(tmp_path, monkeypatch):
    q = tmp_path / "intake_queue.jsonl"
    monkeypatch.setattr(vil, "drain_queue", lambda **kw: _make_drain_report(processed=2))
    vil.check_drain_dry_run(q, verbose=False)
    lines = [ln for ln in q.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) >= 2


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_returns_zero_on_all_pass(monkeypatch, tmp_path, capsys):
    """Patch all check functions to return [] so main() exits 0."""
    monkeypatch.setattr(sys, "argv", ["validate_intake_loop.py"])

    for name in (
        "check_schema_and_decompose",
        "check_self_heal_dry_run",
        "check_two_log_audit",
        "check_auto_intake_cli",
        "check_workflow_go_audit",
        "check_workflow_go_verify",
        "check_drain_dry_run",
    ):
        monkeypatch.setattr(vil, name, lambda *a, **kw: [])

    rc = vil.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "OK" in captured.out


def test_main_returns_one_on_any_failure(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["validate_intake_loop.py"])

    def _fail(*a, **kw):
        return ["something went wrong"]

    for name in (
        "check_schema_and_decompose",
        "check_self_heal_dry_run",
        "check_two_log_audit",
        "check_auto_intake_cli",
        "check_workflow_go_audit",
        "check_workflow_go_verify",
        "check_drain_dry_run",
    ):
        monkeypatch.setattr(vil, name, _fail)

    rc = vil.main()
    assert rc == 1
    captured = capsys.readouterr()
    assert "FAILED" in captured.err
