"""Tests for memory/store.py — SQLite-backed SystemMemoryStore CRUD."""

from __future__ import annotations

import importlib.util
import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------
_RUNTIME = Path(__file__).resolve().parent.parent / "02_RUNTIME"


def _load(name: str, rel: str):
    path = _RUNTIME / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_store_mod = _load("memory.store", "memory/store.py")

SystemMemoryStore = _store_mod.SystemMemoryStore
Learning = _store_mod.Learning
GovernanceRule = _store_mod.GovernanceRule
ScopeViolation = _store_mod.ScopeViolation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "test_memory.sqlite"


@pytest.fixture
def store(db_path) -> SystemMemoryStore:
    return SystemMemoryStore(db_path=db_path)


def _learning(
    lid: str | None = None,
    category: str = "testing",
    scope: str = "cross-cutting",
) -> Learning:
    return Learning(
        id=lid or str(uuid.uuid4()),
        title="Test learning",
        category=category,
        confidence="high",
        scope=scope,
        content="Content body",
        source="pytest",
    )


def _rule(name: str | None = None, category: str = "security", severity: str = "warning") -> GovernanceRule:
    return GovernanceRule(
        id=str(uuid.uuid4()),
        rule_name=name or f"RULE_{uuid.uuid4().hex[:8].upper()}",
        category=category,
        severity=severity,
        description="A test rule",
        enforcement="warn",
        pseudocode_fix="# no-op",
    )


def _violation(mission: str = "M1", task: str = "T1") -> ScopeViolation:
    return ScopeViolation(
        id=str(uuid.uuid4()),
        mission_id=mission,
        task_id=task,
        expected_scope="src/",
        violated_files=["src/other.py", "secret.env"],
        detected_by="scope_magnet",
        resolution="reverted",
        severity="warning",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStore:
    # ------------------------------------------------------------------
    # Learnings — insert and retrieve
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_insert_and_get_learning(self, store):
        l1 = _learning()
        await store.insert_learning(l1)
        rows = await store.get_learnings(active_only=False)
        ids = {r.id for r in rows}
        assert l1.id in ids

    @pytest.mark.asyncio
    async def test_get_learning_filter_by_category(self, store):
        l_test = _learning(category="testing")
        l_sec = _learning(category="security")
        await store.insert_learning(l_test)
        await store.insert_learning(l_sec)
        rows = await store.get_learnings(category="testing", active_only=False)
        assert all(r.category == "testing" for r in rows)
        assert any(r.id == l_test.id for r in rows)

    @pytest.mark.asyncio
    async def test_get_learning_filter_by_scope(self, store):
        l_cc = _learning(scope="cross-cutting")
        l_rs = _learning(scope="repo-specific")
        await store.insert_learning(l_cc)
        await store.insert_learning(l_rs)
        rows = await store.get_learnings(scope="repo-specific", active_only=False)
        assert all(r.scope == "repo-specific" for r in rows)

    @pytest.mark.asyncio
    async def test_get_learnings_respects_active_only(self, store):
        l_active = Learning(
            id=str(uuid.uuid4()),
            title="Active",
            category="testing",
            confidence="high",
            scope="cross-cutting",
            content="body",
            source="test",
            active=True,
        )
        l_inactive = Learning(
            id=str(uuid.uuid4()),
            title="Inactive",
            category="testing",
            confidence="high",
            scope="cross-cutting",
            content="body",
            source="test",
            active=False,
        )
        await store.insert_learning(l_active)
        await store.insert_learning(l_inactive)
        rows = await store.get_learnings(active_only=True)
        ids = {r.id for r in rows}
        assert l_active.id in ids
        assert l_inactive.id not in ids

    @pytest.mark.asyncio
    async def test_insert_learning_upsert(self, store):
        lid = str(uuid.uuid4())
        l1 = Learning(
            id=lid, title="First", category="testing", confidence="high",
            scope="cross-cutting", content="v1", source="test",
        )
        l2 = Learning(
            id=lid, title="Updated", category="testing", confidence="high",
            scope="cross-cutting", content="v2", source="test",
        )
        await store.insert_learning(l1)
        await store.insert_learning(l2)
        rows = await store.get_learnings(active_only=False)
        matching = [r for r in rows if r.id == lid]
        assert len(matching) == 1
        assert matching[0].title == "Updated"

    @pytest.mark.asyncio
    async def test_get_learnings_limit(self, store):
        for _ in range(5):
            await store.insert_learning(_learning())
        rows = await store.get_learnings(active_only=False, limit=3)
        assert len(rows) <= 3

    # ------------------------------------------------------------------
    # Governance Rules
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_governance_rules_empty(self, store):
        # Fresh DB — governance rules are seeded from schema, not from inserts
        rules = await store.get_governance_rules(active_only=True)
        # Schema may or may not pre-seed; just assert it returns a list
        assert isinstance(rules, list)

    @pytest.mark.asyncio
    async def test_get_rule_by_name_not_found(self, store):
        r = await store.get_rule_by_name("NONEXISTENT_RULE_XYZ")
        assert r is None

    # ------------------------------------------------------------------
    # Scope Violations — record and retrieve
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_record_and_get_violation(self, store):
        v = _violation()
        await store.record_violation(v)
        rows = await store.get_violations()
        ids = {r.id for r in rows}
        assert v.id in ids

    @pytest.mark.asyncio
    async def test_violation_files_roundtrip(self, store):
        v = _violation()
        await store.record_violation(v)
        rows = await store.get_violations()
        found = next(r for r in rows if r.id == v.id)
        assert found.violated_files == v.violated_files

    @pytest.mark.asyncio
    async def test_get_violations_filter_by_mission(self, store):
        v1 = _violation(mission="M-ALPHA")
        v2 = _violation(mission="M-BETA")
        await store.record_violation(v1)
        await store.record_violation(v2)
        rows = await store.get_violations(mission_id="M-ALPHA")
        assert all(r.mission_id == "M-ALPHA" for r in rows)

    @pytest.mark.asyncio
    async def test_get_violations_filter_by_severity(self, store):
        v_warn = ScopeViolation(
            id=str(uuid.uuid4()), mission_id="M", task_id="T",
            expected_scope="src/", violated_files=["x.py"],
            detected_by="test", resolution="ok", severity="warning",
        )
        v_crit = ScopeViolation(
            id=str(uuid.uuid4()), mission_id="M", task_id="T",
            expected_scope="src/", violated_files=["y.py"],
            detected_by="test", resolution="ok", severity="critical",
        )
        await store.record_violation(v_warn)
        await store.record_violation(v_crit)
        rows = await store.get_violations(severity="critical")
        assert all(r.severity == "critical" for r in rows)
        assert any(r.id == v_crit.id for r in rows)

    @pytest.mark.asyncio
    async def test_get_violations_limit(self, store):
        for i in range(5):
            await store.record_violation(_violation(mission=f"M{i}"))
        rows = await store.get_violations(limit=2)
        assert len(rows) <= 2

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_start_session_returns_uuid(self, store):
        sid = await store.start_session("agent-1", {"repo": "test"})
        assert sid and len(sid) > 8

    @pytest.mark.asyncio
    async def test_end_session_completes(self, store):
        sid = await store.start_session("agent-2", {})
        # Should not raise
        await store.end_session(sid, "success", ["L1", "L2"])

    # ------------------------------------------------------------------
    # DB path override via tmp_path
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_custom_db_path_used(self, tmp_path):
        custom_path = tmp_path / "custom" / "mem.sqlite"
        s = SystemMemoryStore(db_path=custom_path)
        # Insert and retrieve to prove DB is created at custom path
        l = _learning()
        await s.insert_learning(l)
        assert custom_path.exists()
        rows = await s.get_learnings(active_only=False)
        assert any(r.id == l.id for r in rows)

    # ------------------------------------------------------------------
    # assemble_context
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_assemble_context_returns_keys(self, store):
        ctx = await store.assemble_context()
        assert "governance_rules" in ctx
        assert "recent_learnings" in ctx
        assert "recent_scope_violations" in ctx
        assert "injected_at" in ctx

    @pytest.mark.asyncio
    async def test_assemble_context_includes_cross_cutting_learnings(self, store):
        l_cc = _learning(scope="cross-cutting")
        await store.insert_learning(l_cc)
        ctx = await store.assemble_context()
        titles = [lrn["title"] for lrn in ctx["recent_learnings"]]
        assert l_cc.title in titles
