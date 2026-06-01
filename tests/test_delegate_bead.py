"""Tests for scripts/delegate_bead.py — bead -> local-model delegation.

Network-free: stubs bead text + bd writes and injects a fake router whose
adapter returns canned text, so we test the delegation decision logic and
write-back contract, not Ollama itself.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(REPO / "02_RUNTIME"))

# Import after the sys.path insert above so `router` resolves in CI, where the
# 02_RUNTIME path is not on sys.path at collection time. Keep this import block
# directly after the insert (no statements between) so isort/ruff-fix doesn't
# hoist it back above the path setup. See tests/test_router_autopath.py.
from router.contracts import (  # noqa: E402
    OutputType,
    RouteOutput,
    RouteResponse,
)


def _load_delegate():
    spec = importlib.util.spec_from_file_location("delegate_bead", SCRIPTS / "delegate_bead.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


class _FakeComplexity:
    def __init__(self, level: str):
        self.level = level
        self.confidence = 0.9


class _FakeClassifier:
    def __init__(self, level: str):
        self._level = level

    def classify(self, *_a, **_k):
        return _FakeComplexity(self._level)


class _FakeRouter:
    def __init__(self, level: str, *, error: bool = False):
        self.complexity_classifier = _FakeClassifier(level)
        self._error = error
        self.routed = False

    async def route(self, req):
        self.routed = True
        if self._error:
            return RouteResponse(
                request_id=req.request_id,
                selected_provider="native_claude",
                output=RouteOutput(type=OutputType.ERROR, content="boom"),
            )
        return RouteResponse(
            request_id=req.request_id,
            selected_provider="ollama",
            output=RouteOutput(type=OutputType.TEXT, content="tac"),
        )


def _patch_bd(mod, *, capture: dict):
    mod._bead_text = lambda bid: ("Reverse 'cat'", "mechanical")
    mod._run_bd = lambda args, **k: (capture.__setitem__("args", args) or (0, "ok"))


def test_c1_bead_is_delegated_and_note_written():
    mod = _load_delegate()
    cap: dict = {}
    _patch_bd(mod, capture=cap)
    router = _FakeRouter("C1")
    res = asyncio.run(mod.delegate("b1", max_level="C2", dry_run=False, router=router))
    assert res["delegated"] is True
    assert res["provider"] == "ollama"
    assert res["c_level"] == "C1"
    assert res["bead_note_written"] is True
    assert cap["args"][0] == "update"  # bd update --notes


def test_c4_bead_is_kept_on_orchestrator():
    mod = _load_delegate()
    cap: dict = {}
    _patch_bd(mod, capture=cap)
    router = _FakeRouter("C4")
    res = asyncio.run(mod.delegate("b2", max_level="C2", dry_run=False, router=router))
    assert res["delegated"] is False
    assert router.routed is False  # never even routed
    assert "exceeds max_level" in res["reason"]


def test_dry_run_classifies_without_routing():
    mod = _load_delegate()
    cap: dict = {}
    _patch_bd(mod, capture=cap)
    router = _FakeRouter("C1")
    res = asyncio.run(mod.delegate("b3", max_level="C2", dry_run=True, router=router))
    assert res.get("would_delegate") is True
    assert router.routed is False
    assert cap == {}  # no bd write


def test_delegation_error_does_not_write_note():
    mod = _load_delegate()
    cap: dict = {}
    _patch_bd(mod, capture=cap)
    router = _FakeRouter("C1", error=True)
    res = asyncio.run(mod.delegate("b4", max_level="C2", dry_run=False, router=router))
    assert res["delegated"] is False
    assert res["error"] is True
    assert "bead_note_written" not in res  # no write on error
    assert cap == {}


def test_max_level_widens_delegation():
    mod = _load_delegate()
    cap: dict = {}
    _patch_bd(mod, capture=cap)
    router = _FakeRouter("C3")
    res = asyncio.run(mod.delegate("b5", max_level="C3", dry_run=True, router=router))
    assert res.get("would_delegate") is True


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
