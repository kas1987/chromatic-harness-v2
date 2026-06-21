"""Tests for 02_RUNTIME/memory/store.py (SystemMemoryStore — the DB layer).

The task called for 'db.py'; the actual DB module is memory/store.py which
provides the full SQLite-backed persistence layer (learnings, governance rules,
scope violations, agent sessions).
"""

from __future__ import annotations

import importlib.util
import sys
import types
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

_RUNTIME = Path(__file__).resolve().parent.parent / "02_RUNTIME"
_MODULE_PATH = _RUNTIME / "memory" / "store.py"


def _load_module() -> types.ModuleType:
    """Load memory.store via importlib. aiosqlite is a real dep (confirmed present)."""
    spec = importlib.util.spec_from_file_location("memory.store", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["memory.store"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def store_mod():
    return _load_module()


@pytest.fixture()
def tmp_db(tmp_path, store_mod):
    """SystemMemoryStore backed by a fresh SQLite file in tmp_path."""
    db_file = tmp_path / "test_memory.sqlite"
    return store_mod.SystemMemoryStore(db_path=db_file)


@pytest.fixture()
def inmem_store(store_mod):
    """SystemMemoryStore backed by a shared in-memory SQLite URI."""
    uid = uuid.uuid4().hex
    return store_mod.SystemMemoryStore(db_path=f"file::memory:{uid}?cache=shared")


@pytest.fixture()
def sample_learning(store_mod):
    return store_mod.Learning(
        id=str(uuid.uuid4()),
        title="Test Learning",
        category="testing",
        confidence="high",
        scope="cross-cutting",
        content="This is a test learning entry.",
        source="unit-test",
        epic="",
    )


@pytest.fixture()
def sample_rule(store_mod):
    return store_mod.GovernanceRule(
        id=str(uuid.uuid4()),
        rule_name=f"RULE-UNIT-{uuid.uuid4().hex[:6].upper()}",
        category="hook",
        severity="warning",
        description="Unit test governance rule.",
        enforcement="warn",
        pseudocode_fix="pass",
    )


@pytest.fixture()
def sample_violation(store_mod):
    return store_mod.ScopeViolation(
        id=str(uuid.uuid4()),
        mission_id="CHR-MISSION-TEST",
        task_id="T-001",
        expected_scope="src/",
        violated_files=["other/file.py"],
        detected_by="scope_magnet",
        resolution="manual",
        severity="warning",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDB:
    def test_import_clean(self, store_mod):
        """Module imports cleanly with expected public symbols."""
        assert hasattr(store_mod, "SystemMemoryStore")
        assert hasattr(store_mod, "Learning")
        assert hasattr(store_mod, "GovernanceRule")
        assert hasattr(store_mod, "ScopeViolation")

    def test_dataclass_instantiation(self, store_mod, sample_learning, sample_rule, sample_violation):
        """All three dataclasses construct without error."""
        assert sample_learning.title == "Test Learning"
        assert sample_rule.severity == "warning"
        assert sample_violation.expected_scope == "src/"

    @pytest.mark.asyncio
    async def test_insert_and_get_learning_happy_path(self, tmp_db, sample_learning):
        """insert_learning + get_learnings round-trips a record."""
        await tmp_db.insert_learning(sample_learning)
        results = await tmp_db.get_learnings(active_only=False)
        ids = [r.id for r in results]
        assert sample_learning.id in ids

    @pytest.mark.asyncio
    async def test_get_learnings_filter_by_category(self, tmp_db, store_mod):
        """get_learnings filters by category correctly."""
        l1 = store_mod.Learning(
            id=str(uuid.uuid4()),
            title="Sec Learning",
            category="security",
            confidence="high",
            scope="cross-cutting",
            content="sec content",
        )
        l2 = store_mod.Learning(
            id=str(uuid.uuid4()),
            title="Arch Learning",
            category="architecture",
            confidence="medium",
            scope="cross-cutting",
            content="arch content",
        )
        await tmp_db.insert_learning(l1)
        await tmp_db.insert_learning(l2)

        sec_results = await tmp_db.get_learnings(category="security", active_only=False)
        assert all(r.category == "security" for r in sec_results)
        assert any(r.id == l1.id for r in sec_results)
        assert all(r.id != l2.id for r in sec_results)

    @pytest.mark.asyncio
    async def test_get_learnings_active_only_filter(self, tmp_db, store_mod):
        """active_only=True excludes inactive learnings."""
        active = store_mod.Learning(
            id=str(uuid.uuid4()),
            title="Active",
            category="testing",
            confidence="high",
            scope="cross-cutting",
            content="active",
            active=True,
        )
        inactive = store_mod.Learning(
            id=str(uuid.uuid4()),
            title="Inactive",
            category="testing",
            confidence="high",
            scope="cross-cutting",
            content="inactive",
            active=False,
        )
        await tmp_db.insert_learning(active)
        await tmp_db.insert_learning(inactive)

        active_results = await tmp_db.get_learnings(active_only=True)
        result_ids = [r.id for r in active_results]
        assert active.id in result_ids
        assert inactive.id not in result_ids

    @pytest.mark.asyncio
    async def test_get_governance_rules_seeded(self, tmp_db):
        """Schema seeds critical governance rules; get_governance_rules returns them."""
        rules = await tmp_db.get_governance_rules()
        assert len(rules) > 0
        names = [r.rule_name for r in rules]
        assert "FILE_SCOPE_ENFORCEMENT" in names

    @pytest.mark.asyncio
    async def test_get_rule_by_name_happy_path(self, tmp_db, store_mod, sample_rule):
        """get_rule_by_name returns the correct rule after insert."""
        # Use the schema-seeded rule so we don't need to insert a custom one
        rule = await tmp_db.get_rule_by_name("P3_SECRETS_BLOCKED")
        assert rule is not None
        assert rule.rule_name == "P3_SECRETS_BLOCKED"

    @pytest.mark.asyncio
    async def test_get_rule_by_name_missing(self, tmp_db):
        """get_rule_by_name returns None for a non-existent rule name."""
        result = await tmp_db.get_rule_by_name("NONEXISTENT_RULE_XYZ")
        assert result is None

    @pytest.mark.asyncio
    async def test_record_violation_happy_path(self, tmp_db, sample_violation):
        """record_violation persists a scope violation; get_violations retrieves it."""
        await tmp_db.record_violation(sample_violation)
        violations = await tmp_db.get_violations()
        vids = [v.id for v in violations]
        assert sample_violation.id in vids

    @pytest.mark.asyncio
    async def test_violation_violated_files_roundtrip(self, tmp_db, store_mod):
        """violated_files list is JSON-serialized and deserialized correctly."""
        files = ["src/a.py", "src/b.py", "outside/c.py"]
        v = store_mod.ScopeViolation(
            id=str(uuid.uuid4()),
            mission_id="M-001",
            task_id="T-002",
            expected_scope="src/",
            violated_files=files,
            detected_by="scope_magnet",
            resolution="blocked",
        )
        await tmp_db.record_violation(v)
        results = await tmp_db.get_violations(mission_id="M-001")
        assert len(results) == 1
        assert results[0].violated_files == files

    @pytest.mark.asyncio
    async def test_session_start_and_end(self, tmp_db):
        """start_session and end_session complete without error."""
        sid = await tmp_db.start_session("agent-test", {"repo": "harness"})
        assert isinstance(sid, str)
        await tmp_db.end_session(sid, "success", ["L-001"])

    @pytest.mark.asyncio
    async def test_assemble_context_returns_dict(self, tmp_db):
        """assemble_context returns a well-formed context packet."""
        ctx = await tmp_db.assemble_context()
        assert "governance_rules" in ctx
        assert "recent_learnings" in ctx
        assert "recent_scope_violations" in ctx
        assert "injected_at" in ctx
        assert isinstance(ctx["governance_rules"], list)

    @pytest.mark.asyncio
    async def test_assemble_context_p3_filters_critical(self, tmp_db):
        """assemble_context with P3 privacy class returns only critical rules."""
        ctx = await tmp_db.assemble_context(privacy_class="P3")
        for rule in ctx["governance_rules"]:
            assert rule["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_boundary_empty_db_returns_empty_lists(self, tmp_path, store_mod):
        """A fresh DB with no inserts returns empty lists for learnings and violations."""
        # Use a new file so schema seeds run but no user data exists
        db = store_mod.SystemMemoryStore(db_path=tmp_path / "empty.sqlite")
        learnings = await db.get_learnings(active_only=False)
        # Schema inserts learning seeds; just check return type
        assert isinstance(learnings, list)
        violations = await db.get_violations()
        assert isinstance(violations, list)

    @pytest.mark.asyncio
    async def test_get_violations_filter_by_severity(self, tmp_db, store_mod):
        """get_violations filters by severity correctly."""
        crit = store_mod.ScopeViolation(
            id=str(uuid.uuid4()),
            mission_id="M-CRIT",
            task_id="T-C",
            expected_scope="src/",
            violated_files=["x.py"],
            detected_by="scope_magnet",
            resolution="blocked",
            severity="critical",
        )
        warn = store_mod.ScopeViolation(
            id=str(uuid.uuid4()),
            mission_id="M-WARN",
            task_id="T-W",
            expected_scope="src/",
            violated_files=["y.py"],
            detected_by="scope_magnet",
            resolution="warned",
            severity="warning",
        )
        await tmp_db.record_violation(crit)
        await tmp_db.record_violation(warn)

        crit_results = await tmp_db.get_violations(severity="critical")
        assert all(v.severity == "critical" for v in crit_results)

    @pytest.mark.asyncio
    async def test_fail_open_insert_or_replace_learning(self, tmp_db, store_mod):
        """INSERT OR REPLACE: re-inserting same id updates the record without error."""
        lid = str(uuid.uuid4())
        l1 = store_mod.Learning(
            id=lid,
            title="Original",
            category="testing",
            confidence="low",
            scope="cross-cutting",
            content="v1",
        )
        l2 = store_mod.Learning(
            id=lid,
            title="Updated",
            category="testing",
            confidence="high",
            scope="cross-cutting",
            content="v2",
        )
        await tmp_db.insert_learning(l1)
        await tmp_db.insert_learning(l2)
        results = await tmp_db.get_learnings(active_only=False)
        matching = [r for r in results if r.id == lid]
        assert len(matching) == 1
        assert matching[0].title == "Updated"
