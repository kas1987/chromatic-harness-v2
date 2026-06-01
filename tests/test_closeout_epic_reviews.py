"""Guard for the session-closeout epic-review surfacing.

_run_epic_reviews() rolls up E2E epic ship/no-ship status at session end and
must fail open (never raise), returning a compact summary.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_closeout():
    spec = importlib.util.spec_from_file_location("session_closeout", REPO / "scripts" / "session_closeout.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_epic_reviews_shape_and_failopen():
    mod = _load_closeout()
    result = mod._run_epic_reviews()
    assert isinstance(result, dict)
    assert result["status"] in {"ok", "no_ledger", "error"}
    assert isinstance(result.get("epics"), list)
    if result["status"] == "ok":
        assert "shippable" in result and "total" in result
        for e in result["epics"]:
            assert e["decision"] in {"SHIP", "NO-SHIP"}
            assert "gates_passed" in e and "gates_total" in e


def test_epic_reviews_failopen_on_broken_epic_review(monkeypatch):
    mod = _load_closeout()
    # Force epic_review import path to a module that raises in load_ledger.
    import epic_review  # noqa: PLC0415

    monkeypatch.setattr(epic_review, "load_ledger", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    result = mod._run_epic_reviews()
    assert result["status"] == "error"
    assert result["epics"] == []


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
