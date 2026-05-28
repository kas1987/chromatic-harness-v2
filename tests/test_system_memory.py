"""Tests for System Memory Store and Scope Enforcement."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_RUNTIME = os.path.join(_REPO, "02_RUNTIME")
sys.path.insert(0, _REPO)
sys.path.insert(0, _RUNTIME)

import pytest

from memory.store import SystemMemoryStore, Learning, GovernanceRule, ScopeViolation
from scope.enforcer import ScopeEnforcer, ScopeBaseline, ScopeCheckResult


@pytest.fixture
def temp_db():
    # Use a persistent temp file; Windows may lock it but tests are short-lived
    import tempfile
    f = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    path = f.name
    f.close()
    yield path
    # Best-effort cleanup
    try:
        os.unlink(path)
    except PermissionError:
        pass


@pytest.fixture
def store(temp_db):
    return SystemMemoryStore(db_path=temp_db)


@pytest.mark.asyncio
async def test_get_governance_rules(store):
    rules = await store.get_governance_rules(active_only=True)
    assert len(rules) >= 1
    names = {r.rule_name for r in rules}
    assert "FILE_SCOPE_ENFORCEMENT" in names


@pytest.mark.asyncio
async def test_get_rules_by_category(store):
    rules = await store.get_governance_rules(category="file_scope")
    assert all(r.category == "file_scope" for r in rules)


@pytest.mark.asyncio
async def test_get_learnings(store):
    learnings = await store.get_learnings(scope="cross-cutting", limit=10)
    assert len(learnings) >= 1
    assert all(l.scope == "cross-cutting" for l in learnings)


@pytest.mark.asyncio
async def test_insert_and_retrieve_learning(store):
    l = Learning(
        id="L-TEST-001",
        title="Test Learning",
        category="process",
        confidence="high",
        scope="repo-specific",
        content="Test content for persistent memory.",
        source="test_suite",
    )
    await store.insert_learning(l)
    retrieved = await store.get_learnings(limit=100)
    assert any(r.id == "L-TEST-001" for r in retrieved)


@pytest.mark.asyncio
async def test_assemble_context(store):
    ctx = await store.assemble_context(mission_type="coding", privacy_class="P3")
    assert "governance_rules" in ctx
    assert "recent_learnings" in ctx
    assert "recent_scope_violations" in ctx
    # P3 should pull critical rules
    assert any(r["severity"] == "critical" for r in ctx["governance_rules"])


@pytest.mark.asyncio
async def test_record_and_retrieve_violation(store):
    v = ScopeViolation(
        id="V-TEST-001",
        mission_id="M-001",
        task_id="T-001",
        expected_scope="05_FRONTEND_CONSOLE/",
        violated_files=["02_RUNTIME/router/new_file.py"],
        detected_by="test_enforcer",
        resolution="pending",
        severity="warning",
    )
    await store.record_violation(v)
    violations = await store.get_violations(mission_id="M-001")
    assert len(violations) == 1
    assert violations[0].expected_scope == "05_FRONTEND_CONSOLE/"


@pytest.mark.asyncio
async def test_session_lifecycle(store):
    sid = await store.start_session(agent_id="test-agent", project_context={"repo": "test"})
    assert sid
    await store.end_session(sid, outcome="success", injected_memory=["L-001", "R-001"])


def test_scope_enforcer_baseline():
    with tempfile.TemporaryDirectory() as tmp:
        # Init a git repo for testing
        os.system(f"git init -q {tmp}")
        (Path(tmp) / "05_FRONTEND_CONSOLE" / "file.tsx").parent.mkdir(parents=True, exist_ok=True)
        (Path(tmp) / "05_FRONTEND_CONSOLE" / "file.tsx").write_text("x")
        (Path(tmp) / "02_RUNTIME" / "router.py").parent.mkdir(parents=True, exist_ok=True)
        (Path(tmp) / "02_RUNTIME" / "router.py").write_text("y")
        os.system(f"git -C {tmp} add . && git -C {tmp} commit -q -m 'init'")

        enforcer = ScopeEnforcer(repo_root=tmp)
        baseline = enforcer.take_baseline("M-001", "05_FRONTEND_CONSOLE/")
        assert baseline.baseline_count >= 1


def test_scope_enforcer_passes_when_no_changes():
    with tempfile.TemporaryDirectory() as tmp:
        os.system(f"git init -q {tmp}")
        (Path(tmp) / "05_FRONTEND_CONSOLE" / "file.tsx").parent.mkdir(parents=True, exist_ok=True)
        (Path(tmp) / "05_FRONTEND_CONSOLE" / "file.tsx").write_text("x")
        os.system(f"git -C {tmp} add . && git -C {tmp} commit -q -m 'init'")

        enforcer = ScopeEnforcer(repo_root=tmp)
        baseline = enforcer.take_baseline("M-001", "05_FRONTEND_CONSOLE/")
        result = enforcer.check_scope(baseline)
        assert result.passed is True


def test_scope_enforcer_detects_out_of_scope_file():
    with tempfile.TemporaryDirectory() as tmp:
        os.system(f"git init -q {tmp}")
        (Path(tmp) / "05_FRONTEND_CONSOLE" / "file.tsx").parent.mkdir(parents=True, exist_ok=True)
        (Path(tmp) / "05_FRONTEND_CONSOLE" / "file.tsx").write_text("x")
        os.system(f"git -C {tmp} add . && git -C {tmp} commit -q -m 'init'")

        # Take baseline BEFORE injecting out-of-scope file
        enforcer = ScopeEnforcer(repo_root=tmp)
        baseline = enforcer.take_baseline("M-001", "05_FRONTEND_CONSOLE/")

        # Now create out-of-scope file (simulates worker scope violation)
        (Path(tmp) / "02_RUNTIME" / "bad.py").parent.mkdir(parents=True, exist_ok=True)
        (Path(tmp) / "02_RUNTIME" / "bad.py").write_text("injected")

        result = enforcer.check_scope(baseline)
        assert result.passed is False
        assert any("02_RUNTIME" in v for v in result.violations)


def test_scope_header_generation():
    enforcer = ScopeEnforcer()
    rules = [{"severity": "critical", "name": "TEST", "description": "desc", "fix": "fix_code"}]
    header = enforcer.build_scope_header("05_FRONTEND_CONSOLE/", rules)
    assert "FILE SCOPE: 05_FRONTEND_CONSOLE/" in header
    assert "TEST" in header
    assert "fix_code" in header
