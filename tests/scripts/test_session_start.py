"""Unit tests for scripts/session_start.py.

Tests cover: lean-boot helpers, _is_fresh, _forecast_line_from_cache,
_bd_argv, _bd, _inject_ready_queue, _surface_for_runtime, _emit_baseline_alerts,
and the main() entry point (happy path + guard-not-found).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO / "scripts" / "session_start.py"

# Load the module once; the module-level stream-reconfigure call is safe.
_spec = importlib.util.spec_from_file_location("session_start", _SCRIPT)
_ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ss)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# _lean_boot
# ---------------------------------------------------------------------------


def test_lean_boot_off_by_default(monkeypatch):
    monkeypatch.delenv("CHROMATIC_LEAN_BOOT", raising=False)
    assert _ss._lean_boot() is False


@pytest.mark.parametrize("val", ["1", "true", "yes", "TRUE", "YES"])
def test_lean_boot_on_for_truthy_values(monkeypatch, val):
    monkeypatch.setenv("CHROMATIC_LEAN_BOOT", val)
    assert _ss._lean_boot() is True


@pytest.mark.parametrize("val", ["0", "false", "no", ""])
def test_lean_boot_off_for_falsy_values(monkeypatch, val):
    monkeypatch.setenv("CHROMATIC_LEAN_BOOT", val)
    assert _ss._lean_boot() is False


# ---------------------------------------------------------------------------
# _is_fresh
# ---------------------------------------------------------------------------


def test_is_fresh_true_for_new_file(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{}", encoding="utf-8")
    assert _ss._is_fresh(p, hours=6) is True


def test_is_fresh_false_for_old_file(tmp_path):
    import os

    p = tmp_path / "x.json"
    p.write_text("{}", encoding="utf-8")
    old = time.time() - 7 * 3600
    os.utime(p, (old, old))
    assert _ss._is_fresh(p, hours=6) is False


def test_is_fresh_false_for_missing_file():
    assert _ss._is_fresh(Path("/nonexistent/path.json")) is False


# ---------------------------------------------------------------------------
# _forecast_line_from_cache
# ---------------------------------------------------------------------------


def test_forecast_line_from_cache_returns_line(tmp_path, monkeypatch):
    snap = {
        "boot": {"estimated_tokens": 1447},
        "burn": {
            "daily_spent_usd": 1.0,
            "weekly_spent_usd": 2.0,
            "weekly_trend_pct": 0.0,
        },
        "forecast": {
            "risk_level": "green",
            "end_of_day_usd": 3.0,
            "end_of_week_usd": 4.0,
            "end_of_month_usd": 5.0,
        },
        "limits": {"weekly": {"current_usd": 1.0, "cap_usd": 100.0}},
        "model_usage": {},
    }
    p = tmp_path / "forecast_latest.json"
    p.write_text(json.dumps(snap), encoding="utf-8")
    monkeypatch.setattr(_ss, "_FORECAST_LATEST", p)
    line = _ss._forecast_line_from_cache()
    assert line is not None
    assert "boot 1,447t" in line and "[G]" in line


def test_forecast_line_from_cache_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(_ss, "_FORECAST_LATEST", tmp_path / "absent.json")
    assert _ss._forecast_line_from_cache() is None


def test_forecast_line_from_cache_none_on_invalid_json(tmp_path, monkeypatch):
    p = tmp_path / "bad.json"
    p.write_text("NOT JSON", encoding="utf-8")
    monkeypatch.setattr(_ss, "_FORECAST_LATEST", p)
    # Should fail-open (return None), not raise
    result = _ss._forecast_line_from_cache()
    assert result is None


# ---------------------------------------------------------------------------
# _bd_argv
# ---------------------------------------------------------------------------


def test_bd_argv_uses_which_when_found(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/bd" if name == "bd" else None)
    argv = _ss._bd_argv(["prime"])
    assert argv == ["/usr/bin/bd", "prime"]


def test_bd_argv_falls_back_to_cmd_when_not_found(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    argv = _ss._bd_argv(["ready"])
    assert argv[:3] == ["cmd", "/c", "bd"]
    assert "ready" in argv


# ---------------------------------------------------------------------------
# _bd
# ---------------------------------------------------------------------------


def test_bd_returns_code_and_stdout(monkeypatch):
    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stdout = "bead-1: some task\n"

    monkeypatch.setattr(_ss, "run_safe", lambda *a, **kw: fake_result)
    code, out = _ss._bd(["ready"])
    assert code == 0
    assert "bead-1" in out


def test_bd_returns_nonzero_on_failure(monkeypatch):
    fake_result = MagicMock()
    fake_result.returncode = 1
    fake_result.stdout = ""

    monkeypatch.setattr(_ss, "run_safe", lambda *a, **kw: fake_result)
    code, out = _ss._bd(["list"])
    assert code == 1
    assert out == ""


# ---------------------------------------------------------------------------
# _inject_ready_queue
# ---------------------------------------------------------------------------


def test_inject_ready_queue_prints_lines(monkeypatch, capsys):
    monkeypatch.setattr(_ss, "_bd", lambda args, timeout=20: (0, "task-1: Do something\ntask-2: Another task\n"))
    _ss._inject_ready_queue()
    captured = capsys.readouterr()
    assert "task-1" in captured.out
    assert "task-2" in captured.out


def test_inject_ready_queue_silent_on_failure(monkeypatch, capsys):
    monkeypatch.setattr(_ss, "_bd", lambda args, timeout=20: (1, ""))
    _ss._inject_ready_queue()
    captured = capsys.readouterr()
    # Nothing printed when bd fails
    assert "task" not in captured.out


def test_inject_ready_queue_silent_on_empty(monkeypatch, capsys):
    monkeypatch.setattr(_ss, "_bd", lambda args, timeout=20: (0, ""))
    _ss._inject_ready_queue()
    captured = capsys.readouterr()
    assert "Ready beads" not in captured.out


# ---------------------------------------------------------------------------
# _surface_for_runtime
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "runtime,expected",
    [
        ("claude", "cli"),
        ("cli", "cli"),
        ("cursor", "cursor"),
        ("vscode", "vscode"),
        ("app", "app"),
        ("unknown_value", "cli"),
    ],
)
def test_surface_for_runtime(monkeypatch, runtime, expected):
    monkeypatch.setenv("CHROMATIC_RUNTIME", runtime)
    assert _ss._surface_for_runtime() == expected


def test_surface_for_runtime_default_when_unset(monkeypatch):
    monkeypatch.delenv("CHROMATIC_RUNTIME", raising=False)
    assert _ss._surface_for_runtime() == "cli"


# ---------------------------------------------------------------------------
# _emit_baseline_alerts
# ---------------------------------------------------------------------------


def test_emit_baseline_alerts_prints_ok(monkeypatch, capsys):
    monkeypatch.setattr(
        _ss,
        "_call_audit_surface",
        lambda surface: {"overall": "ok", "metrics": {}},
    )
    monkeypatch.setattr(_ss, "_surface_for_runtime", lambda: "cli")
    _ss._emit_baseline_alerts()
    captured = capsys.readouterr()
    assert "[ok]" in captured.out


def test_emit_baseline_alerts_prints_warn_metrics(monkeypatch, capsys):
    monkeypatch.setattr(
        _ss,
        "_call_audit_surface",
        lambda surface: {
            "overall": "warn",
            "metrics": {
                "token_budget": {
                    "status": "warn",
                    "value": 95,
                    "advice": "reduce context",
                }
            },
        },
    )
    monkeypatch.setattr(_ss, "_surface_for_runtime", lambda: "cli")
    _ss._emit_baseline_alerts()
    captured = capsys.readouterr()
    assert "[warn]" in captured.out
    assert "token_budget" in captured.out


def test_emit_baseline_alerts_fails_open_on_exception(monkeypatch, capsys):
    monkeypatch.setattr(_ss, "_call_audit_surface", lambda surface: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(_ss, "_surface_for_runtime", lambda: "cli")
    # Must not raise; writes to stderr
    _ss._emit_baseline_alerts()
    captured = capsys.readouterr()
    assert "baseline drift: skipped" in captured.err


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_returns_zero_with_guard_missing(tmp_path, monkeypatch, capsys):
    """main() returns 0 even when the guard script is absent (graceful skip)."""
    fake_guard = tmp_path / "no_such_guard.py"  # does NOT exist

    monkeypatch.setattr(_ss, "_REPO", tmp_path)
    monkeypatch.setattr(_ss, "_GUARD", fake_guard)
    monkeypatch.setattr(_ss, "_HANDOFF", tmp_path / "no_handoff.json")
    monkeypatch.setattr(_ss, "_OPS", tmp_path / "AGENT_OPERATIONS.md")
    monkeypatch.setattr(_ss, "_MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(_ss, "_HEALTH", tmp_path / "health.json")
    monkeypatch.setattr(_ss, "_BUDGET_FORECAST", tmp_path / "no_forecast.py")
    monkeypatch.setattr(_ss, "_emit_boot", lambda cold: None)
    monkeypatch.setattr(_ss, "_inject_learnings", lambda: None)
    monkeypatch.setattr(_ss, "_inject_ready_queue", lambda limit=8: None)
    monkeypatch.setattr(_ss, "_emit_baseline_alerts", lambda: None)
    monkeypatch.setattr(_ss, "_emit_ci_health", lambda: None)
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: None)

    rc = _ss.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "session_unified_guard.py not found" in captured.out


def test_main_prints_handoff_when_present(tmp_path, monkeypatch, capsys):
    handoff = tmp_path / "latest.json"
    handoff.write_text('{"session": "test-session"}', encoding="utf-8")

    monkeypatch.setattr(_ss, "_REPO", tmp_path)
    monkeypatch.setattr(_ss, "_GUARD", tmp_path / "no_guard.py")
    monkeypatch.setattr(_ss, "_HANDOFF", handoff)
    monkeypatch.setattr(_ss, "_OPS", tmp_path / "AGENT_OPERATIONS.md")
    monkeypatch.setattr(_ss, "_MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(_ss, "_HEALTH", tmp_path / "health.json")
    monkeypatch.setattr(_ss, "_BUDGET_FORECAST", tmp_path / "no_forecast.py")
    monkeypatch.setattr(_ss, "_emit_boot", lambda cold: None)
    monkeypatch.setattr(_ss, "_inject_learnings", lambda: None)
    monkeypatch.setattr(_ss, "_inject_ready_queue", lambda limit=8: None)
    monkeypatch.setattr(_ss, "_emit_baseline_alerts", lambda: None)
    monkeypatch.setattr(_ss, "_emit_ci_health", lambda: None)
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: None)

    rc = _ss.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "test-session" in captured.out
    assert "No handoff file" not in captured.out


def test_main_reads_manifest_json(tmp_path, monkeypatch, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "generated_at": "2026-06-01T10:00:00Z",
                "branch": "feat/test-branch",
                "mcp_audit": {"estimated_tokens_if_enabled": 12345},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(_ss, "_REPO", tmp_path)
    monkeypatch.setattr(_ss, "_GUARD", tmp_path / "no_guard.py")
    monkeypatch.setattr(_ss, "_HANDOFF", tmp_path / "no_handoff.json")
    monkeypatch.setattr(_ss, "_OPS", tmp_path / "AGENT_OPERATIONS.md")
    monkeypatch.setattr(_ss, "_MANIFEST", manifest)
    monkeypatch.setattr(_ss, "_HEALTH", tmp_path / "health.json")
    monkeypatch.setattr(_ss, "_BUDGET_FORECAST", tmp_path / "no_forecast.py")
    monkeypatch.setattr(_ss, "_emit_boot", lambda cold: None)
    monkeypatch.setattr(_ss, "_inject_learnings", lambda: None)
    monkeypatch.setattr(_ss, "_inject_ready_queue", lambda limit=8: None)
    monkeypatch.setattr(_ss, "_emit_baseline_alerts", lambda: None)
    monkeypatch.setattr(_ss, "_emit_ci_health", lambda: None)
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: None)

    rc = _ss.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "feat/test-branch" in captured.out
    assert "12,345" in captured.out


def test_main_reads_health_json(tmp_path, monkeypatch, capsys):
    health = tmp_path / "health.json"
    health.write_text(
        json.dumps(
            {
                "overall_status": "green",
                "readiness_score": 92,
                "counts": {"pass": 10, "warn": 1, "fail": 0},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(_ss, "_REPO", tmp_path)
    monkeypatch.setattr(_ss, "_GUARD", tmp_path / "no_guard.py")
    monkeypatch.setattr(_ss, "_HANDOFF", tmp_path / "no_handoff.json")
    monkeypatch.setattr(_ss, "_OPS", tmp_path / "AGENT_OPERATIONS.md")
    monkeypatch.setattr(_ss, "_MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(_ss, "_HEALTH", health)
    monkeypatch.setattr(_ss, "_BUDGET_FORECAST", tmp_path / "no_forecast.py")
    monkeypatch.setattr(_ss, "_emit_boot", lambda cold: None)
    monkeypatch.setattr(_ss, "_inject_learnings", lambda: None)
    monkeypatch.setattr(_ss, "_inject_ready_queue", lambda limit=8: None)
    monkeypatch.setattr(_ss, "_emit_baseline_alerts", lambda: None)
    monkeypatch.setattr(_ss, "_emit_ci_health", lambda: None)
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: None)

    rc = _ss.main()
    assert rc == 0
    captured = capsys.readouterr()
    assert "readiness_status: green" in captured.out
    assert "readiness_score: 92" in captured.out
    assert "checks(pass/warn/fail): 10/1/0" in captured.out
