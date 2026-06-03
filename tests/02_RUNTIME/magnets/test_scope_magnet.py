"""Tests for magnets.scope_magnet — ScopeMagnet.

The ScopeMagnet has a heavy dependency on ScopeEnforcer / SystemMemoryStore
(requires aiosqlite) and uses a relative import (``from ..scope.enforcer``)
inside ``observe()`` when enforcement is triggered.

All external integrations are mocked so the tests stay self-contained.

Testing strategy:
- Interface / non-enforcement paths: simple unit tests (no mocks needed).
- Enforcement path (baseline with expected_scope): we intercept the inline
  relative import via builtins.__import__ so no package hierarchy is needed.
"""

from __future__ import annotations

import builtins
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# ---- Stub out heavy top-level imports before ScopeMagnet is loaded ----
_fake_memory = MagicMock()
_fake_scope_mod = MagicMock()
_fake_memory.SystemMemoryStore = MagicMock(return_value=MagicMock())
_fake_scope_mod.ScopeEnforcer = MagicMock(return_value=MagicMock())
_FakeScopeBaseline = MagicMock(return_value=MagicMock())
_fake_scope_mod.ScopeBaseline = _FakeScopeBaseline

import pytest

from magnets.base_magnet import BaseMagnet, MagnetEvent
from magnets.scope_magnet import ScopeMagnet


@pytest.fixture(autouse=True, scope="module")
def _isolate_scope_sys_modules():
    """Prevent module-level scope/memory stubs from leaking into the rest of the session."""
    saved = {}
    for key in ("scope", "scope.enforcer", "memory", "memory.store"):
        saved[key] = sys.modules.pop(key, None)
    sys.modules["scope"] = _fake_scope_mod
    sys.modules["scope.enforcer"] = _fake_scope_mod
    sys.modules["memory"] = _fake_memory
    sys.modules["memory.store"] = _fake_memory
    yield
    for key, val in saved.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val


class TestScopeMagnetInterface:
    def test_is_base_magnet_subclass(self):
        assert issubclass(ScopeMagnet, BaseMagnet)

    def test_name(self):
        assert ScopeMagnet.name == "scope_magnet"

    def test_observe_returns_magnet_event(self):
        m = ScopeMagnet()
        event = m.observe("m1", "intake", {})
        assert isinstance(event, MagnetEvent)


class TestScopeMagnetNonPostExecution:
    """Non post_execution inflection points return a plain pass-through event."""

    def test_intake_inflection_no_delta(self):
        event = ScopeMagnet().observe("m1", "intake", {})
        assert event.risk_delta == 0.0
        assert event.confidence_delta == 0.0

    def test_dispatch_inflection_no_evidence(self):
        event = ScopeMagnet().observe("m1", "dispatch", {"file_scope": ["x.py"]})
        assert event.evidence == []

    def test_non_execution_preserves_signal(self):
        sig = {"note": "hello"}
        event = ScopeMagnet().observe("m1", "plan", sig)
        assert event.observed_signal is sig

    def test_non_execution_default_action(self):
        event = ScopeMagnet().observe("m1", "plan", {})
        assert event.recommended_action == "none"


class TestScopeMagnetPostExecutionNoBaseline:
    """post_execution with file_scope but without scope_baseline returns plain event."""

    def test_no_baseline_no_risk(self):
        event = ScopeMagnet().observe("m1", "post_execution", {"file_scope": ["src/a.py"]})
        assert event.risk_delta == 0.0

    def test_no_file_scope_no_enforcement(self):
        event = ScopeMagnet().observe("m1", "post_execution", {})
        assert event.risk_delta == 0.0

    def test_baseline_without_expected_scope_skips_enforcement(self):
        event = ScopeMagnet().observe(
            "m1",
            "post_execution",
            {
                "file_scope": ["src/a.py"],
                "scope_baseline": {"baseline_count": 5},  # missing expected_scope key
            },
        )
        assert event.risk_delta == 0.0

    def test_no_file_scope_with_baseline_skips_enforcement(self):
        """Without file_scope key, enforcement is not triggered."""
        event = ScopeMagnet().observe(
            "m1",
            "post_execution",
            {"scope_baseline": {"expected_scope": ["src/"], "baseline_count": 1}},
        )
        assert event.risk_delta == 0.0


def _intercept_relative_import(fake_scope_baseline):
    """Return a context manager that intercepts the 'from ..scope.enforcer import ScopeBaseline'
    relative import inside ScopeMagnet.observe() by wrapping builtins.__import__.

    The relative import `from ..scope.enforcer import ScopeBaseline` is equivalent
    to __import__('scope.enforcer', globals, locals, ['ScopeBaseline'], 2).
    We intercept that specific call and return the fake.
    """
    real_import = builtins.__import__

    def patched_import(name, *args, **kwargs):
        # Catch the relative import of scope.enforcer
        fromlist = args[2] if len(args) > 2 else kwargs.get("fromlist", ())
        if "scope" in (name or "") and "ScopeBaseline" in (fromlist or []):
            mod = MagicMock()
            mod.ScopeBaseline = fake_scope_baseline
            return mod
        return real_import(name, *args, **kwargs)

    return patch("builtins.__import__", side_effect=patched_import)


class TestScopeMagnetPostExecutionWithViolations:
    """post_execution with a scope_baseline that has expected_scope triggers enforcement."""

    def _make_violation_result(self, violations):
        result = MagicMock()
        result.passed = False
        result.violations = violations
        return result

    def _observe_with_violations(self, violations):
        violation_result = self._make_violation_result(violations)
        fake_baseline_cls = MagicMock(return_value=MagicMock())

        enforcer_inst = MagicMock()
        enforcer_inst.enforce_and_log = AsyncMock(return_value=violation_result)

        m = ScopeMagnet()
        m.enforcer = enforcer_inst

        with (
            _intercept_relative_import(fake_baseline_cls),
            patch("asyncio.get_event_loop") as mock_loop,
        ):
            mock_loop.return_value.run_until_complete.return_value = violation_result
            event = m.observe(
                "m1",
                "post_execution",
                {
                    "file_scope": ["src/a.py"],
                    "scope_baseline": {
                        "expected_scope": ["src/a.py"],
                        "baseline_count": len(violations),
                    },
                },
            )
        return event

    def test_violations_increase_risk(self):
        event = self._observe_with_violations(["file_a.py touched outside scope"])
        assert event.risk_delta > 0.0

    def test_violations_recommend_halt_and_revert(self):
        event = self._observe_with_violations(["out_of_scope.py modified"])
        assert event.recommended_action == "halt_and_revert"

    def test_violations_stored_in_evidence(self):
        violations = ["file1.py", "file2.py"]
        event = self._observe_with_violations(violations)
        for v in violations:
            assert v in event.evidence

    def test_risk_capped_at_1_0(self):
        # 7 violations * 0.15 = 1.05 -> should cap at 1.0
        violations = [f"file{i}.py" for i in range(7)]
        event = self._observe_with_violations(violations)
        assert event.risk_delta <= 1.0

    def test_single_violation_risk_0_15(self):
        event = self._observe_with_violations(["one_file.py"])
        assert event.risk_delta == 0.15
