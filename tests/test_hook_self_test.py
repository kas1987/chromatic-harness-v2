"""Smoke tests for hook_self_test.py (gh-80 / NW-RG-080).

Reconciled from EPIC-B (shipped untested) — these gate the script in the pre-push
suite so it cannot silently rot. Network-free; runs against the repo's own hooks.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("hook_self_test", REPO / "scripts" / "hook_self_test.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["hook_self_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_run_self_test_shape():
    mod = _load()
    result = mod.run_self_test()
    assert result["harness_component"] == "hook_self_test"
    assert result["overall"] in {"pass", "warn", "fail"}
    assert "summary" in result and "critical_hooks" in result


def test_critical_hooks_listed():
    mod = _load()
    result = mod.run_self_test()
    crit = result["critical_hooks"]
    assert isinstance(crit, list) and len(crit) >= 1
    for c in crit:
        assert c["status"] in {"pass", "fail"}


def test_extract_commands_flattens():
    mod = _load()
    settings = {"hooks": {"PreToolUse": [{"matcher": "", "hooks": [{"command": "python x.py", "timeout": 10}]}]}}
    out = mod._extract_commands(settings, "test")
    assert out and out[0]["command"] == "python x.py" and out[0]["event"] == "PreToolUse"


def test_syntax_ok_on_self():
    mod = _load()
    ok, _ = mod._syntax_ok(REPO / "scripts" / "hook_self_test.py")
    assert ok is True  # the script must itself be syntactically valid


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
