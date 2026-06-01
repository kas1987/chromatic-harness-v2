"""Tests for -477a: change-gated quality (ruff/pytest) in session_closeout."""

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("session_closeout", _REPO / "scripts" / "session_closeout.py")
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)  # type: ignore


def _patch_run(monkeypatch, mapping):
    def fake_run(cmd, *, timeout=120, cwd=None):
        joined = " ".join(cmd)
        for key, val in mapping.items():
            if key in joined:
                return val
        return 0, ""

    monkeypatch.setattr(sc, "_run", fake_run)


def test_no_change_skips_all(monkeypatch):
    monkeypatch.setattr(sc, "_changed_code_files", lambda: [])
    r = sc.run_change_gated_quality(run_pytest=True)
    assert r["code_changed"] is False
    assert r["ruff"] is None and r["pytest"] is None


def test_changed_py_runs_ruff_and_pytest(monkeypatch):
    monkeypatch.setattr(sc, "_changed_code_files", lambda: ["a.py"])
    _patch_run(monkeypatch, {"ruff": (0, "All checks passed"), "pytest": (0, "1 passed")})
    r = sc.run_change_gated_quality(run_pytest=True)
    assert r["ruff"]["ok"] and r["pytest"]["ok"]


def test_pytest_skipped_when_disabled(monkeypatch):
    monkeypatch.setattr(sc, "_changed_code_files", lambda: ["a.py"])
    _patch_run(monkeypatch, {"ruff": (0, "ok")})
    r = sc.run_change_gated_quality(run_pytest=False)
    assert r["ruff"] is not None and r["pytest"] is None


def test_non_py_change_skips_ruff(monkeypatch):
    monkeypatch.setattr(sc, "_changed_code_files", lambda: ["main.go"])
    _patch_run(monkeypatch, {"pytest": (0, "ok")})
    r = sc.run_change_gated_quality(run_pytest=True)
    assert r["code_changed"] is True
    assert r["ruff"] is None


def test_ruff_failure_surfaced(monkeypatch):
    monkeypatch.setattr(sc, "_changed_code_files", lambda: ["a.py"])
    _patch_run(monkeypatch, {"ruff": (1, "E501 line too long"), "pytest": (0, "ok")})
    r = sc.run_change_gated_quality(run_pytest=True)
    assert r["ruff"]["ok"] is False
