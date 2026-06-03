"""Tests for scope/guard.py — DispatchGuard and GuardedMission."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_RUNTIME = Path(__file__).resolve().parents[4] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

# ---------------------------------------------------------------------------
# Stub leaf dependencies that aren't installed in this environment.
# aiosqlite: used by memory.store for async DB access.
# subprocess git: called inside scope.enforcer — we patch at the class level
# after import so no OS call is needed.
# ---------------------------------------------------------------------------
if "aiosqlite" not in sys.modules:
    sys.modules["aiosqlite"] = MagicMock()

# Now we can safely import the module under test.
from scope.guard import DispatchGuard, GuardedMission  # noqa: E402


# ---------------------------------------------------------------------------
# Helper factories — build isolated mocks per test so tests don't share state.
# We bypass __init__ and directly set the two dependencies that guard.py uses:
# self.memory (SystemMemoryStore) and self.enforcer (ScopeEnforcer).
# ---------------------------------------------------------------------------


def _make_store():
    store = MagicMock()
    store.assemble_context = AsyncMock(return_value={})
    store.start_session = AsyncMock()
    return store


def _make_enforcer():
    baseline = MagicMock()
    baseline.mission_id = "m1"
    baseline.expected_scope = "src/"
    baseline.baseline_count = 5
    enforcer = MagicMock()
    enforcer.take_baseline = MagicMock(return_value=baseline)
    enforcer.build_scope_header = MagicMock(return_value="SCOPE HEADER")
    return enforcer, baseline


def _fresh_guard():
    """Return a DispatchGuard with fully isolated mock objects, no real DB/git."""
    store = _make_store()
    enforcer, baseline = _make_enforcer()
    guard = DispatchGuard.__new__(DispatchGuard)
    guard.memory = store
    guard.enforcer = enforcer
    return guard, store, enforcer, baseline


# ---------------------------------------------------------------------------
# Tests: return type and basic structure
# ---------------------------------------------------------------------------


class TestDispatchGuardReturnType:
    @pytest.mark.asyncio
    async def test_returns_guarded_mission(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"mission_id": "m1", "objective": "do stuff"})
        assert isinstance(result, GuardedMission)

    @pytest.mark.asyncio
    async def test_mission_is_preserved(self):
        guard, _, _, _ = _fresh_guard()
        mission = {"mission_id": "m1", "objective": "do stuff"}
        result = await guard.guard(mission)
        assert result.mission is mission

    @pytest.mark.asyncio
    async def test_injected_context_from_memory(self):
        guard, store, _, _ = _fresh_guard()
        store.assemble_context = AsyncMock(return_value={"key": "value"})
        result = await guard.guard({"mission_id": "m1"})
        assert result.injected_context == {"key": "value"}

    @pytest.mark.asyncio
    async def test_scope_header_from_enforcer(self):
        guard, _, enforcer, _ = _fresh_guard()
        enforcer.build_scope_header = MagicMock(return_value="MY HEADER")
        result = await guard.guard({"mission_id": "m1"})
        assert result.scope_header == "MY HEADER"


# ---------------------------------------------------------------------------
# Tests: scope baseline creation
# ---------------------------------------------------------------------------


class TestDispatchGuardScopeBaseline:
    @pytest.mark.asyncio
    async def test_no_file_scope_gives_no_baseline(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"mission_id": "m1"})
        assert result.scope_baseline is None

    @pytest.mark.asyncio
    async def test_file_scope_triggers_take_baseline(self):
        guard, _, enforcer, baseline = _fresh_guard()
        result = await guard.guard({"mission_id": "m1"}, file_scope="src/")
        enforcer.take_baseline.assert_called_once_with("m1", "src/")
        assert result.scope_baseline is baseline

    @pytest.mark.asyncio
    async def test_empty_file_scope_string_gives_no_baseline(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"mission_id": "m1"}, file_scope="")
        assert result.scope_baseline is None

    @pytest.mark.asyncio
    async def test_baseline_metadata_embedded_in_mission(self):
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
    async def test_no_baseline_metadata_is_empty_dict(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"mission_id": "m1"})
        assert result.mission["metadata"]["chromatic_scope_baseline"] == {}


# ---------------------------------------------------------------------------
# Tests: memory interaction
# ---------------------------------------------------------------------------


class TestDispatchGuardMemoryInteraction:
    @pytest.mark.asyncio
    async def test_assemble_context_called_with_mission_type(self):
        guard, store, _, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1", "objective": "run linter"})
        call_kwargs = store.assemble_context.call_args
        assert call_kwargs.kwargs["mission_type"] == "run linter"

    @pytest.mark.asyncio
    async def test_assemble_context_uses_privacy_class(self):
        guard, store, _, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1", "privacy_class": "P3"})
        call_kwargs = store.assemble_context.call_args
        assert call_kwargs.kwargs["privacy_class"] == "P3"

    @pytest.mark.asyncio
    async def test_assemble_context_default_privacy_class(self):
        guard, store, _, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1"})
        call_kwargs = store.assemble_context.call_args
        assert call_kwargs.kwargs["privacy_class"] == "P1"

    @pytest.mark.asyncio
    async def test_start_session_called_with_agent_id(self):
        guard, store, _, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1"}, agent_id="worker-7")
        call_kwargs = store.start_session.call_args
        assert call_kwargs.kwargs["agent_id"] == "worker-7"

    @pytest.mark.asyncio
    async def test_start_session_default_agent_id(self):
        guard, store, _, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1"})
        call_kwargs = store.start_session.call_args
        assert call_kwargs.kwargs["agent_id"] == "unknown"

    @pytest.mark.asyncio
    async def test_context_embedded_in_mission_metadata(self):
        guard, store, _, _ = _fresh_guard()
        store.assemble_context = AsyncMock(return_value={"rules": ["r1"]})
        result = await guard.guard({"mission_id": "m1"})
        assert result.mission["metadata"]["chromatic_context"] == {"rules": ["r1"]}


# ---------------------------------------------------------------------------
# Tests: scope header
# ---------------------------------------------------------------------------


class TestDispatchGuardScopeHeader:
    @pytest.mark.asyncio
    async def test_scope_header_embedded_in_metadata(self):
        guard, _, enforcer, _ = _fresh_guard()
        enforcer.build_scope_header = MagicMock(return_value="HEADER_TEXT")
        result = await guard.guard({"mission_id": "m1"})
        assert result.mission["metadata"]["chromatic_scope_header"] == "HEADER_TEXT"

    @pytest.mark.asyncio
    async def test_build_scope_header_receives_file_scope(self):
        guard, _, enforcer, _ = _fresh_guard()
        await guard.guard({"mission_id": "m1"}, file_scope="02_RUNTIME/")
        call_args = enforcer.build_scope_header.call_args
        assert call_args.args[0] == "02_RUNTIME/"

    @pytest.mark.asyncio
    async def test_build_scope_header_receives_governance_rules(self):
        guard, store, enforcer, _ = _fresh_guard()
        rules = [{"severity": "high", "name": "no-rm", "description": "no remove"}]
        store.assemble_context = AsyncMock(return_value={"governance_rules": rules})
        await guard.guard({"mission_id": "m1"})
        call_args = enforcer.build_scope_header.call_args
        assert call_args.args[1] == rules


# ---------------------------------------------------------------------------
# Tests: edge cases / mission dict handling
# ---------------------------------------------------------------------------


class TestDispatchGuardMissionHandling:
    @pytest.mark.asyncio
    async def test_missing_mission_id_defaults_gracefully(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"objective": "do things"})
        assert isinstance(result, GuardedMission)

    @pytest.mark.asyncio
    async def test_existing_metadata_keys_preserved(self):
        guard, _, _, _ = _fresh_guard()
        mission = {"mission_id": "m1", "metadata": {"existing_key": "existing_val"}}
        result = await guard.guard(mission)
        assert result.mission["metadata"]["existing_key"] == "existing_val"

    @pytest.mark.asyncio
    async def test_objective_truncated_to_50_chars_for_context(self):
        guard, store, _, _ = _fresh_guard()
        long_obj = "a" * 100
        await guard.guard({"mission_id": "m1", "objective": long_obj})
        call_kwargs = store.assemble_context.call_args
        assert len(call_kwargs.kwargs["mission_type"]) == 50

    @pytest.mark.asyncio
    async def test_guarded_mission_has_four_fields(self):
        guard, _, _, _ = _fresh_guard()
        result = await guard.guard({"mission_id": "m1"})
        assert hasattr(result, "mission")
        assert hasattr(result, "scope_baseline")
        assert hasattr(result, "injected_context")
        assert hasattr(result, "scope_header")
