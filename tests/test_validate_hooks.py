"""Smoke tests for hooks/validate_hooks.py (gh-80 / NW-RG-080).

Reconciled from EPIC-B (shipped untested). Network-free.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("validate_hooks", REPO / "scripts" / "hooks" / "validate_hooks.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["validate_hooks"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_validate_all_returns_list():
    mod = _load()
    results = mod.validate_all()
    assert isinstance(results, list)
    for r in results:
        assert r["status"] in {"pass", "warn", "fail"}
        assert "command" in r and "findings" in r


def test_validate_all_no_probe_no_exit_codes():
    mod = _load()
    results = mod.validate_all(probe=False)
    # Without probing, no entry should carry a probe exit-code finding.
    assert all(not any("exit_code_" in f for f in r["findings"]) for r in results)


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
