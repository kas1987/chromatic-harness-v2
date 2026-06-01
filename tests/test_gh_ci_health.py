"""Tests for the gh-backed CI-health probe (no network — runner injected)."""

import importlib.util
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("gh_ci_health", _REPO / "scripts" / "gh_ci_health.py")
ghc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ghc)  # type: ignore


def _runner(perms, runs):
    def run(cmd):
        joined = " ".join(cmd)
        if "actions/permissions" in joined:
            return (0, json.dumps(perms)) if perms is not None else (127, "gh: error")
        if "run list" in joined:
            return (0, json.dumps(runs)) if runs is not None else (127, "gh: error")
        return 0, "[]"

    return run


def test_healthy_when_enabled_and_last_success():
    v = ghc.check_ci_health(gh=_runner({"enabled": True}, [{"status": "completed", "conclusion": "success"}]))
    assert v["status"] == "ok"
    assert v["actions_enabled"] is True


def test_fail_when_actions_disabled():
    v = ghc.check_ci_health(gh=_runner({"enabled": False}, [{"status": "completed", "conclusion": "success"}]))
    assert v["status"] == "fail"
    assert any("DISABLED" in r for r in v["reasons"])


def test_warn_when_last_run_failed():
    v = ghc.check_ci_health(gh=_runner({"enabled": True}, [{"status": "completed", "conclusion": "failure"}]))
    assert v["status"] == "warn"
    assert v["last_conclusion"] == "failure"


def test_warn_when_no_runs():
    v = ghc.check_ci_health(gh=_runner({"enabled": True}, []))
    assert v["status"] == "warn"
    assert any("no runs" in r for r in v["reasons"])


def test_disabled_beats_failed_run_severity():
    v = ghc.check_ci_health(gh=_runner({"enabled": False}, [{"status": "completed", "conclusion": "failure"}]))
    assert v["status"] == "fail"


def test_gh_unavailable_is_warn_not_crash():
    v = ghc.check_ci_health(gh=_runner(None, None))
    assert v["status"] == "warn"
    assert v["actions_enabled"] is None


def test_main_exit_2_on_fail(monkeypatch, capsys):
    monkeypatch.setattr(ghc, "check_ci_health", lambda **kw: {"status": "fail", "reasons": []})
    assert ghc.main([]) == 2
    assert "fail" in capsys.readouterr().out


def test_main_exit_0_on_ok(monkeypatch):
    monkeypatch.setattr(ghc, "check_ci_health", lambda **kw: {"status": "ok", "reasons": []})
    assert ghc.main([]) == 0
