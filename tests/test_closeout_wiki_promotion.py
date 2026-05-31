"""Tests for promote_learnings_to_wiki in session_closeout."""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: register stub modules that session_closeout imports at module level
# so importlib.util can load it without the full runtime installed.
# ---------------------------------------------------------------------------


def _stub(name: str, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules.setdefault(name, m)
    return m


# Minimal BudgetLedger stub
class _FakeLedger:
    def snapshot(self):
        snap = MagicMock()
        snap.decision = "continue"
        snap.reasons = []
        snap.session_est_tokens = 0
        snap.to_budget_dict.return_value = {}
        return snap


_stub("budget", BudgetLedger=_FakeLedger)
_stub("budget.ledger", BudgetLedger=_FakeLedger)
_stub(
    "budget.transfer_packet",
    build_transfer_packet=lambda *a, **kw: {},
    write_transfer_artifacts=lambda *a, **kw: None,
)
_stub(
    "orchestrator.session_compact",
    write_handoff=lambda *a, **kw: Path("/tmp/handoff.md"),
)

# Load session_closeout via importlib so we don't need it on PYTHONPATH
_SC_PATH = Path(__file__).resolve().parents[1] / "scripts" / "session_closeout.py"
_spec = importlib.util.spec_from_file_location("session_closeout", _SC_PATH)
assert _spec and _spec.loader
_sc = importlib.util.module_from_spec(_spec)
sys.modules["session_closeout"] = _sc
_spec.loader.exec_module(_sc)  # type: ignore[union-attr]

promote_learnings_to_wiki = _sc.promote_learnings_to_wiki


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _runner_ok(promoted: int = 3):
    """Fake runner that returns success JSON with `promoted` count."""
    payload = json.dumps({"promoted": promoted, "candidates": 5, "execute": True})

    def _run(cmd):
        return 0, payload

    return _run


def _runner_nonzero():
    def _run(cmd):
        return 1, "some error output"

    return _run


def _runner_bad_json():
    def _run(cmd):
        return 0, "not-json-at-all"

    return _run


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_success_path_parses_promoted_count():
    result = promote_learnings_to_wiki(execute=True, runner=_runner_ok(3))
    assert result["ok"] is True
    assert result["promoted"] == 3
    assert result["skipped_reason"] == ""


def test_nonzero_exit_returns_ok_false():
    result = promote_learnings_to_wiki(execute=True, runner=_runner_nonzero())
    assert result["ok"] is False
    assert result["promoted"] == 0
    assert "exited 1" in result["skipped_reason"]


def test_malformed_json_returns_ok_false_fail_open():
    result = promote_learnings_to_wiki(execute=True, runner=_runner_bad_json())
    assert result["ok"] is False
    assert result["promoted"] == 0
    assert "malformed JSON" in result["skipped_reason"]


def test_does_not_raise_on_unexpected_runner_error():
    def _bad_runner(cmd):
        raise RuntimeError("boom")

    result = promote_learnings_to_wiki(execute=True, runner=_bad_runner)
    assert result["ok"] is False
    assert "boom" in result["skipped_reason"]
