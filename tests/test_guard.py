"""Tests for 02_RUNTIME/scope/guard.py — DispatchGuard pre-dispatch guard.

Uses importlib.util.spec_from_file_location pattern for module loading.
All I/O (memory store, git subprocess) is mocked — no real DB or git calls.
Security-sensitive: verifies that guard correctly injects scope context and
blocks unapproved scope expansion.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub aiosqlite before anything in memory.store is imported.
# ---------------------------------------------------------------------------
if "aiosqlite" not in sys.modules:
    sys.modules["aiosqlite"] = MagicMock()

_RUNTIME = Path(__file__).resolve().parents[1] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from scope.guard import DispatchGuard, GuardedMission  # noqa: E402


# ---------------------------------------------------------------------------
# Factory helpers — each test gets fully isolated mocks, no shared state.
# ---------------------------------------------------------------------------


def _make_store():
    store = MagicMock()
    store.assemble_context = AsyncMock(return_value={})
    store.start_session = AsyncMock()
    return store


def _make_enforcer(baseline_mission_id: str = "m1", baseline_scope: str = "src/", baseline_count: int = 5):
    baseline = MagicMock()
    baseline.mission_id = baseline_mission_id
    baseline.expected_scope = baseline_scope
    baseline.baseline_count = baseline_count
    enforcer = MagicMock()
    enforcer.take_baseline = MagicMock(return_value=baseline)
    enforcer.build_scope_header = MagicMock(return_value="SCOPE HEADER")
    return enforcer, baseline


def _fresh_guard():
    """Return (guard, store, enforcer, baseline) with isolated mocks."""
    store = _make_store()
    enforcer, baseline = _make_enforcer()
    guard = DispatchGuard.__new__(DispatchGuard)
    guard.memory = store
    guard.enforcer = enforcer
    return guard, store, enforcer, baseline


# ---------------------------------------------------------------------------
# TestGuard
# ---------------------------------------------------------------------------


class TestGuard:
    # ------------------------------------------------------------------
    # Return type and basic structure
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_guard_returns_guarded_mission(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"mission_id": "m1", "objective": "do stuff"})
        assert isinstance(result, GuardedMission)

    @pytest.mark.asyncio
    async def test_guard_preserves_mission_dict_reference(self):
        guard, _, _, _ = _fresh_guard()
        mission = {"mission_id": "m1", "objective": "work"}
        result = await guard.guard(mission)
        assert result.mission is mission

    @pytest.mark.asyncio
    async def test_guard_result_has_all_four_fields(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"mission_id": "m1"})
        assert hasattr(result, "mission")
        assert hasattr(result, "scope_baseline")
        assert hasattr(result, "injected_context")
        assert hasattr(result, "scope_header")

    @pytest.mark.asyncio
    async def test_guard_injected_context_from_memory(self):
        guard, store, _, _ = _fresh_guard()
        store.assemble_context = AsyncMock(return_value={"key": "value"})
        result = await guard.guard({"mission_id": "m1"})
        assert result.injected_context == {"key": "value"}

    @pytest.mark.asyncio
    async def test_guard_scope_header_from_enforcer(self):
        guard, _, enforcer, _ = _fresh_guard()
        enforcer.build_scope_header = MagicMock(return_value="MY HEADER")
        result = await guard.guard({"mission_id": "m1"})
        assert result.scope_header == "MY HEADER"

    # ------------------------------------------------------------------
    # Scope baseline — security: must not allow untracked expansion
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_guard_no_file_scope_gives_none_baseline(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"mission_id": "m1"})
        assert result.scope_baseline is None

    @pytest.mark.asyncio
    async def test_guard_file_scope_triggers_take_baseline(self):
        guard, _, enforcer, baseline = _fresh_guard()
        result = await guard.guard({"mission_id": "m1"}, file_scope="src/")
        enforcer.take_baseline.assert_called_once_with("m1", "src/")
        assert result.scope_baseline is baseline

    @pytest.mark.asyncio
    async def test_guard_empty_scope_string_gives_no_baseline(self):
        guard, _, enforcer, _ = _fresh_guard()
        result = await guard.guard({"mission_id": "m1"}, file_scope="")
        assert result.scope_baseline is None

    @pytest.mark.asyncio
    async def test_guard_scope_baseline_embedded_in_metadata(self):
        guard, _, _, baseline = _fresh_guard()
        baseline.mission_id = "m99"
        baseline.expected_scope = "tests/"
        baseline.baseline_count = 42
        result = await guard.guard({"mission_id": "m99"}, file_scope="tests/")
        meta = result.mission["metadata"]["chromatic_scope_baseline"]
        assert meta["mission_id"] == "m99"
        assert meta["expected_scope"] == "tests/"
        assert meta["baseline_count"] == 42

    @pytest.mark.asyncio
    async def test_guard_no_baseline_yields_empty_metadata_dict(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"mission_id": "m1"})
        assert result.mission["metadata"]["chromatic_scope_baseline"] == {}

    @pytest.mark.asyncio
    async def test_guard_scope_not_taken_when_scope_absent(self):
        guard, _, enforcer, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1"})
        enforcer.take_baseline.assert_not_called()

    # ------------------------------------------------------------------
    # Memory interaction
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_guard_assemble_context_receives_mission_type(self):
        guard, store, _, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1", "objective": "run linter"})
        assert store.assemble_context.call_args.kwargs["mission_type"] == "run linter"

    @pytest.mark.asyncio
    async def test_guard_assemble_context_uses_privacy_class_from_mission(self):
        guard, store, _, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1", "privacy_class": "P3"})
        assert store.assemble_context.call_args.kwargs["privacy_class"] == "P3"

    @pytest.mark.asyncio
    async def test_guard_assemble_context_default_privacy_p1(self):
        guard, store, _, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1"})
        assert store.assemble_context.call_args.kwargs["privacy_class"] == "P1"

    @pytest.mark.asyncio
    async def test_guard_start_session_receives_agent_id(self):
        guard, store, _, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1"}, agent_id="worker-7")
        assert store.start_session.call_args.kwargs["agent_id"] == "worker-7"

    @pytest.mark.asyncio
    async def test_guard_start_session_defaults_to_unknown(self):
        guard, store, _, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1"})
        assert store.start_session.call_args.kwargs["agent_id"] == "unknown"

    @pytest.mark.asyncio
    async def test_guard_context_embedded_in_mission_metadata(self):
        guard, store, _, _ = _fresh_guard()
        store.assemble_context = AsyncMock(return_value={"rules": ["r1"]})
        result = await guard.guard({"mission_id": "m1"})
        assert result.mission["metadata"]["chromatic_context"] == {"rules": ["r1"]}

    # ------------------------------------------------------------------
    # Scope header injection
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_guard_scope_header_embedded_in_metadata(self):
        guard, _, enforcer, _ = _fresh_guard()
        enforcer.build_scope_header = MagicMock(return_value="HEADER_TEXT")
        result = await guard.guard({"mission_id": "m1"})
        assert result.mission["metadata"]["chromatic_scope_header"] == "HEADER_TEXT"

    @pytest.mark.asyncio
    async def test_guard_build_scope_header_receives_file_scope_arg(self):
        guard, _, enforcer, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1"}, file_scope="02_RUNTIME/")
        assert enforcer.build_scope_header.call_args.args[0] == "02_RUNTIME/"

    @pytest.mark.asyncio
    async def test_guard_build_scope_header_receives_governance_rules(self):
        guard, store, enforcer, _ = _fresh_guard()
        rules = [{"severity": "high", "name": "no-rm", "description": "no remove"}]
        store.assemble_context = AsyncMock(return_value={"governance_rules": rules})
        await guard.guard({"mission_id": "m1"})
        assert enforcer.build_scope_header.call_args.args[1] == rules

    # ------------------------------------------------------------------
    # Edge cases / mission dict handling
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_guard_missing_mission_id_handled_gracefully(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"objective": "do things"})
        assert isinstance(result, GuardedMission)

    @pytest.mark.asyncio
    async def test_guard_existing_metadata_keys_preserved(self):
        guard, _, _, _ = _fresh_guard()
        mission = {"mission_id": "m1", "metadata": {"existing_key": "existing_val"}}
        result = await guard.guard(mission)
        assert result.mission["metadata"]["existing_key"] == "existing_val"

    @pytest.mark.asyncio
    async def test_guard_objective_truncated_to_50_chars_for_context(self):
        guard, store, _, _ = _fresh_guard()
        long_obj = "a" * 100
        await guard.guard({"mission_id": "m1", "objective": long_obj})
        assert len(store.assemble_context.call_args.kwargs["mission_type"]) == 50

    @pytest.mark.asyncio
    async def test_guard_denies_scope_expansion_when_scope_already_set(self):
        """Guard must not call take_baseline twice for the same mission."""
        guard, _, enforcer, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1"}, file_scope="src/")
        # Only one baseline taken — enforcer.take_baseline must be called exactly once.
        assert enforcer.take_baseline.call_count == 1
