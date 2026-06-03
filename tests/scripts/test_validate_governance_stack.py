"""Unit tests for scripts/validate_governance_stack.py.

Tests the main() function with mocked run_safe so no external subprocesses
are launched. Covers: all-pass, single gate failure, context_trim special
handling (risk_level red/orange/green), daily_audit_strict JSON check,
and the --strict-audit flag.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "scripts" / "validate_governance_stack.py"

_spec = importlib.util.spec_from_file_location("validate_governance_stack", _SCRIPT)
vgs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vgs)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_ok_result(stdout: str = "", stderr: str = "") -> MagicMock:
    r = MagicMock()
    r.returncode = 0
    r.stdout = stdout
    r.stderr = stderr
    return r


def _make_fail_result(stdout: str = "", stderr: str = "error output") -> MagicMock:
    r = MagicMock()
    r.returncode = 1
    r.stdout = stdout
    r.stderr = stderr
    return r


# ---------------------------------------------------------------------------
# _context_trim_ok
# ---------------------------------------------------------------------------


def test_context_trim_ok_returns_true_for_green():
    assert vgs._context_trim_ok("Risk level: green") is True


def test_context_trim_ok_returns_false_for_red():
    assert vgs._context_trim_ok('"risk_level": "red"') is False


def test_context_trim_ok_returns_false_for_orange():
    assert vgs._context_trim_ok('"risk_level": "orange"') is False


def test_context_trim_ok_returns_true_for_empty():
    assert vgs._context_trim_ok("") is True


# ---------------------------------------------------------------------------
# main() - happy path
# ---------------------------------------------------------------------------


def test_main_all_gates_pass(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate_governance_stack.py"])

    call_log: list[str] = []

    def fake_run_safe(cmd, cwd=None, timeout=600):
        call_log.append(cmd[0] if isinstance(cmd, list) else cmd)
        return _make_ok_result(stdout="Risk level: green")

    monkeypatch.setattr(vgs, "run_safe", fake_run_safe)
    rc = vgs.main()
    assert rc == 0


def test_main_single_gate_fails(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate_governance_stack.py"])

    def fake_run_safe(cmd, cwd=None, timeout=600):
        # Fail agent_operations, pass everything else
        if "check_agent_operations" in " ".join(cmd):
            return _make_fail_result(stderr="ops check failed")
        return _make_ok_result(stdout="Risk level: green")

    monkeypatch.setattr(vgs, "run_safe", fake_run_safe)
    rc = vgs.main()
    assert rc == 1


def test_main_multiple_gates_fail(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate_governance_stack.py"])

    def fake_run_safe(cmd, cwd=None, timeout=600):
        return _make_fail_result()

    monkeypatch.setattr(vgs, "run_safe", fake_run_safe)
    rc = vgs.main()
    assert rc == 1


# ---------------------------------------------------------------------------
# context_trim special handling
# ---------------------------------------------------------------------------


def test_main_context_trim_red_risk_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["validate_governance_stack.py"])

    def fake_run_safe(cmd, cwd=None, timeout=600):
        if "context_trim_audit" in " ".join(cmd):
            return _make_ok_result(stdout='"risk_level": "red"')
        return _make_ok_result(stdout="Risk level: green")

    monkeypatch.setattr(vgs, "run_safe", fake_run_safe)
    rc = vgs.main()
    assert rc == 1


def test_main_context_trim_green_json_file_passes(monkeypatch, tmp_path):
    """When stdout doesn't say 'Risk level: green', fall back to audit JSON."""
    monkeypatch.setattr(sys, "argv", ["validate_governance_stack.py"])

    audit_json = tmp_path / ".agents" / "context" / "context_trim_audit.json"
    audit_json.parent.mkdir(parents=True)
    audit_json.write_text(json.dumps({"risk_level": "green"}), encoding="utf-8")

    def fake_run_safe(cmd, cwd=None, timeout=600):
        if "context_trim_audit" in " ".join(cmd):
            return _make_ok_result(stdout="some output without green marker")
        return _make_ok_result(stdout="Risk level: green")

    monkeypatch.setattr(vgs, "run_safe", fake_run_safe)
    # Patch REPO so the audit JSON path resolves to tmp_path
    monkeypatch.setattr(vgs, "REPO", tmp_path)
    rc = vgs.main()
    assert rc == 0


# ---------------------------------------------------------------------------
# --strict-audit flag
# ---------------------------------------------------------------------------


def test_main_strict_audit_passes_on_green_json(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate_governance_stack.py", "--strict-audit"])

    def fake_run_safe(cmd, cwd=None, timeout=600):
        if "daily_harness_audit" in " ".join(cmd):
            return _make_ok_result(stdout=json.dumps({"status": "green"}))
        return _make_ok_result(stdout="Risk level: green")

    monkeypatch.setattr(vgs, "run_safe", fake_run_safe)
    rc = vgs.main()
    assert rc == 0


def test_main_strict_audit_fails_on_non_green_status(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate_governance_stack.py", "--strict-audit"])

    def fake_run_safe(cmd, cwd=None, timeout=600):
        if "daily_harness_audit" in " ".join(cmd):
            return _make_ok_result(stdout=json.dumps({"status": "yellow"}))
        return _make_ok_result(stdout="Risk level: green")

    monkeypatch.setattr(vgs, "run_safe", fake_run_safe)
    rc = vgs.main()
    assert rc == 1


def test_main_strict_audit_fails_on_invalid_json(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["validate_governance_stack.py", "--strict-audit"])

    def fake_run_safe(cmd, cwd=None, timeout=600):
        if "daily_harness_audit" in " ".join(cmd):
            return _make_ok_result(stdout="NOT JSON")
        return _make_ok_result(stdout="Risk level: green")

    monkeypatch.setattr(vgs, "run_safe", fake_run_safe)
    rc = vgs.main()
    assert rc == 1
