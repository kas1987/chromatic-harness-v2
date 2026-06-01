"""Tests for the local CI gate runner."""

import importlib.util
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ci_local", _REPO / "scripts" / "ci_local.py")
cl = importlib.util.module_from_spec(_spec)
sys.modules["ci_local"] = cl  # required so @dataclass can resolve cls.__module__
_spec.loader.exec_module(cl)  # type: ignore


def test_pre_commit_is_fast_subset():
    gates = cl.select_gates("pre-commit", set())
    names = {g.name for g in gates}
    assert names == {"ruff-check", "ruff-format"}
    assert all(g.fast for g in gates)


def test_pre_push_is_full():
    gates = cl.select_gates("pre-push", set())
    names = {g.name for g in gates}
    assert {"mypy", "pytest", "agent-ops-guard"} <= names


def test_skip_drops_named_gates():
    gates = cl.select_gates("pre-push", {"mypy", "pytest"})
    names = {g.name for g in gates}
    assert "mypy" not in names and "pytest" not in names


def test_run_gates_reports_per_gate():
    gates = cl.select_gates("pre-commit", set())
    calls = []

    def fake(cmd):
        calls.append(cmd)
        return 0 if "check" in cmd else 1  # ruff-check passes, ruff-format fails

    results = cl.run_gates(gates, runner=fake)
    assert results["ruff-check"] == 0
    assert results["ruff-format"] == 1
    assert len(calls) == 2


def test_main_returns_failure_count(monkeypatch):
    monkeypatch.setattr(cl, "run_gates", lambda gates, **k: {"ruff-check": 0, "ruff-format": 1})
    assert cl.main(["--stage", "pre-commit"]) == 1


def test_main_zero_on_all_pass(monkeypatch):
    monkeypatch.setattr(cl, "run_gates", lambda gates, **k: {"ruff-check": 0})
    assert cl.main(["--stage", "pre-commit"]) == 0


def test_list_mode(capsys):
    rc = cl.main(["--stage", "pre-commit", "--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ruff-check:" in out
