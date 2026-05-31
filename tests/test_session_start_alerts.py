"""Tests for _emit_baseline_alerts, _emit_ci_health, _surface_for_runtime in session_start.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load_session_start():
    spec = importlib.util.spec_from_file_location(
        "session_start", _SCRIPTS / "session_start.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ss():
    return _load_session_start()


# ── _surface_for_runtime ─────────────────────────────────────────────────────


def test_surface_for_runtime_default(ss, monkeypatch):
    monkeypatch.delenv("CHROMATIC_RUNTIME", raising=False)
    assert ss._surface_for_runtime() == "cli"


def test_surface_for_runtime_cursor(ss, monkeypatch):
    monkeypatch.setenv("CHROMATIC_RUNTIME", "cursor")
    assert ss._surface_for_runtime() == "cursor"


def test_surface_for_runtime_unknown_falls_back(ss, monkeypatch):
    monkeypatch.setenv("CHROMATIC_RUNTIME", "jetbrains")
    assert ss._surface_for_runtime() == "cli"


# ── _emit_baseline_alerts ────────────────────────────────────────────────────

_AUDIT_OK = {
    "overall": "ok",
    "metrics": {
        "mcp_tokens": {"value": 10, "status": "ok", "advice": ""},
    },
}

_AUDIT_DRIFT = {
    "overall": "over",
    "metrics": {
        "mcp_tokens": {
            "value": 9999,
            "warn": 5000,
            "max": 8000,
            "status": "over",
            "advice": "reduce MCP servers",
        },
        "hook_count": {
            "value": 3,
            "warn": 5,
            "max": 8,
            "status": "warn",
            "advice": "trim hooks",
        },
        "env_keys": {"value": 2, "status": "ok", "advice": ""},
    },
}


def test_baseline_alerts_all_ok(ss, capsys, monkeypatch):
    monkeypatch.delenv("CHROMATIC_RUNTIME", raising=False)
    with patch.object(ss, "_call_audit_surface", return_value=_AUDIT_OK):
        ss._emit_baseline_alerts()
    out = capsys.readouterr().out
    assert "[ok]" in out
    assert "within baseline" in out


def test_baseline_alerts_drift_printed_with_advice(ss, capsys, monkeypatch):
    monkeypatch.delenv("CHROMATIC_RUNTIME", raising=False)
    with patch.object(ss, "_call_audit_surface", return_value=_AUDIT_DRIFT):
        ss._emit_baseline_alerts()
    out = capsys.readouterr().out
    assert "[over]" in out
    assert "reduce MCP servers" in out
    assert "[warn]" in out
    assert "trim hooks" in out
    # ok metric must NOT appear
    assert "env_keys" not in out


def test_baseline_alerts_fail_open_on_exception(ss, capsys):
    with patch.object(ss, "_call_audit_surface", side_effect=RuntimeError("boom")):
        ss._emit_baseline_alerts()  # must not raise
    err = capsys.readouterr().err
    assert "baseline drift: skipped" in err


# ── _emit_ci_health ──────────────────────────────────────────────────────────


def test_ci_health_ok_prints_nothing(ss, capsys):
    with patch.object(
        ss, "_call_ci_health", return_value={"status": "ok", "reasons": []}
    ):
        ss._emit_ci_health()
    assert capsys.readouterr().out == ""


def test_ci_health_fail_prints_warning(ss, capsys):
    with patch.object(
        ss,
        "_call_ci_health",
        return_value={
            "status": "fail",
            "reasons": ["GitHub Actions is DISABLED at the repo level"],
        },
    ):
        ss._emit_ci_health()
    out = capsys.readouterr().out
    assert "[CI-FAIL]" in out
    assert "DISABLED" in out


def test_ci_health_warn_prints_warning(ss, capsys):
    with patch.object(
        ss,
        "_call_ci_health",
        return_value={"status": "warn", "reasons": ["no runs found for ci.yml"]},
    ):
        ss._emit_ci_health()
    out = capsys.readouterr().out
    assert "[CI-WARN]" in out


def test_ci_health_fail_open_on_exception(ss, capsys):
    with patch.object(ss, "_call_ci_health", side_effect=RuntimeError("gh not found")):
        ss._emit_ci_health()  # must not raise
    cap = capsys.readouterr()
    assert cap.out == ""
