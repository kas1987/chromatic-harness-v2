"""Tests for 02_RUNTIME/memory/ — memory_gate.py and store.py."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from memory.memory_gate import (  # noqa: E402
    MemoryWriteError,
    _load_store,
    _save_store,
    _simple_contradiction_score,
    detect_contradiction,
    gate_memory_write,
    list_memories,
    read_memory,
    validate_inputs,
)
from memory.store import (  # noqa: E402
    GovernanceRule,
    Learning,
    ScopeViolation,
    SystemMemoryStore,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> SystemMemoryStore:
    return SystemMemoryStore(db_path=tmp_path / f"mem_{uuid.uuid4().hex}.sqlite")


# ---------------------------------------------------------------------------
# memory_gate — validate_inputs
# ---------------------------------------------------------------------------


def test_validate_inputs_valid():
    errors = validate_inputs("key", "value", "evidence", 0.8, "agent")
    assert errors == []


def test_validate_inputs_empty_key():
    errors = validate_inputs("", "value", "evidence", 0.8, "agent")
    assert any("key" in e for e in errors)


def test_validate_inputs_whitespace_key():
    errors = validate_inputs("   ", "value", "evidence", 0.8, "agent")
    assert any("key" in e for e in errors)


def test_validate_inputs_none_value():
    errors = validate_inputs("key", None, "evidence", 0.8, "agent")
    assert any("value" in e for e in errors)


def test_validate_inputs_empty_evidence():
    errors = validate_inputs("key", "value", "", 0.8, "agent")
    assert errors


def test_validate_inputs_whitespace_evidence():
    errors = validate_inputs("key", "value", "   ", 0.8, "agent")
    assert errors


def test_validate_inputs_confidence_too_high():
    errors = validate_inputs("key", "value", "evidence", 1.5, "agent")
    assert errors


def test_validate_inputs_confidence_negative():
    errors = validate_inputs("key", "value", "evidence", -0.1, "agent")
    assert errors


def test_validate_inputs_confidence_non_numeric():
    errors = validate_inputs("key", "value", "evidence", "high", "agent")
    assert errors


def test_validate_inputs_empty_author():
    errors = validate_inputs("key", "value", "evidence", 0.8, "")
    assert any("author" in e for e in errors)


def test_validate_inputs_multiple_errors():
    errors = validate_inputs("", None, "", -1.0, "")
    assert len(errors) >= 3


# ---------------------------------------------------------------------------
# memory_gate — _simple_contradiction_score
# ---------------------------------------------------------------------------


def test_contradiction_score_identical():
    assert _simple_contradiction_score("foo", "foo") == 0.0


def test_contradiction_score_bool_opposite():
    score = _simple_contradiction_score(True, False)
    assert score == 1.0


def test_contradiction_score_bool_same():
    score = _simple_contradiction_score(True, True)
    assert score == 0.0


def test_contradiction_score_negation_detected():
    score = _simple_contradiction_score("enabled", "not enabled")
    assert score >= 0.5


def test_contradiction_score_numeric_close():
    score = _simple_contradiction_score(100.0, 101.0)
    assert score < 0.1


def test_contradiction_score_numeric_far():
    score = _simple_contradiction_score(1.0, 100.0)
    assert score > 0.5


def test_contradiction_score_type_mismatch():
    score = _simple_contradiction_score("hello", 42)
    assert 0.0 < score <= 1.0


def test_contradiction_score_different_strings_no_negation():
    score = _simple_contradiction_score("alpha", "beta")
    assert 0.0 < score < 0.5


# ---------------------------------------------------------------------------
# memory_gate — detect_contradiction
# ---------------------------------------------------------------------------


def test_detect_contradiction_missing_key():
    store: dict = {}
    result = detect_contradiction("absent", "value", 0.9, store)
    assert result is None


def test_detect_contradiction_low_new_confidence():
    store = {"key": {"value": True, "confidence": 0.9}}
    # low new_confidence should not trigger quarantine
    result = detect_contradiction("key", False, 0.5, store)
    assert result is None


def test_detect_contradiction_boolean_conflict_high_confidence():
    store = {"key": {"value": True, "confidence": 0.9, "author": "a", "timestamp": "t"}}
    result = detect_contradiction("key", False, 0.8, store)
    assert result is not None
    assert result["conflict_score"] == 1.0


def test_detect_contradiction_returns_conflict_record_fields():
    store = {
        "k": {
            "value": "enabled",
            "confidence": 0.8,
            "author": "agent",
            "timestamp": "2026-01-01T00:00:00Z",
        }
    }
    result = detect_contradiction("k", "not enabled", 0.85, store)
    assert result is not None
    assert "key" in result
    assert "existing_value" in result
    assert "new_value" in result


# ---------------------------------------------------------------------------
# memory_gate — gate_memory_write (dry_run — no filesystem side effects)
# ---------------------------------------------------------------------------


def test_gate_dry_run_high_confidence(tmp_path):
    with (
        patch("memory.memory_gate.GATED_STORE", tmp_path / "gs.json"),
        patch("memory.memory_gate.QUARANTINE_STORE", tmp_path / "qs.json"),
        patch("memory.memory_gate.GATE_AUDIT_DIR", tmp_path),
        patch("memory.memory_gate.PROVENANCE_LOG", tmp_path / "prov.jsonl"),
    ):
        result = gate_memory_write("k.test", "val", "evidence text", 0.9, "agent", dry_run=True)
    assert result["status"] == "dry_run"
    assert result.get("would_write") is True


def test_gate_low_confidence_quarantined(tmp_path):
    with (
        patch("memory.memory_gate.GATED_STORE", tmp_path / "gs.json"),
        patch("memory.memory_gate.QUARANTINE_STORE", tmp_path / "qs.json"),
        patch("memory.memory_gate.GATE_AUDIT_DIR", tmp_path),
        patch("memory.memory_gate.PROVENANCE_LOG", tmp_path / "prov.jsonl"),
    ):
        result = gate_memory_write("k.test", "val", "evidence text", 0.2, "agent", dry_run=False)
    assert result["status"] == "quarantined"


def test_gate_validation_error_raises():
    with pytest.raises(MemoryWriteError):
        gate_memory_write("", None, "", -1.0, "", dry_run=True)


def test_gate_write_persists(tmp_path):
    gs = tmp_path / "gs.json"
    with (
        patch("memory.memory_gate.GATED_STORE", gs),
        patch("memory.memory_gate.QUARANTINE_STORE", tmp_path / "qs.json"),
        patch("memory.memory_gate.GATE_AUDIT_DIR", tmp_path),
        patch("memory.memory_gate.PROVENANCE_LOG", tmp_path / "prov.jsonl"),
    ):
        result = gate_memory_write("persist.key", "hello", "solid evidence", 0.9, "tester")
    assert result["status"] == "written"
    stored = json.loads(gs.read_text())
    assert "persist.key" in stored


def test_gate_contradiction_quarantines(tmp_path):
    gs = tmp_path / "gs.json"
    # Pre-load a True value with high confidence.
    gs.write_text(
        json.dumps({"bool.key": {"value": True, "confidence": 0.9, "author": "a", "timestamp": "t"}}),
        encoding="utf-8",
    )
    with (
        patch("memory.memory_gate.GATED_STORE", gs),
        patch("memory.memory_gate.QUARANTINE_STORE", tmp_path / "qs.json"),
        patch("memory.memory_gate.GATE_AUDIT_DIR", tmp_path),
        patch("memory.memory_gate.PROVENANCE_LOG", tmp_path / "prov.jsonl"),
    ):
        result = gate_memory_write("bool.key", False, "new evidence", 0.85, "tester")
    assert result["status"] == "quarantined"
    assert result["contradiction"] is not None


# ---------------------------------------------------------------------------
# memory_gate — _load_store / _save_store helpers
# ---------------------------------------------------------------------------


def test_load_store_missing_file(tmp_path):
    data = _load_store(tmp_path / "nonexistent.json")
    assert data == {}


def test_load_store_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    data = _load_store(bad)
    assert data == {}


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "store.json"
    original = {"key": {"value": 42, "confidence": 0.9}}
    _save_store(path, original)
    loaded = _load_store(path)
    assert loaded == original


# ---------------------------------------------------------------------------
# memory_gate — read_memory / list_memories
# ---------------------------------------------------------------------------


def test_read_memory_returns_none_if_absent(tmp_path):
    with patch("memory.memory_gate.GATED_STORE", tmp_path / "empty.json"):
        result = read_memory("missing.key")
    assert result is None


def test_read_memory_returns_record(tmp_path):
    gs = tmp_path / "gs.json"
    gs.write_text(
        json.dumps({"found.key": {"value": "yes", "confidence": 0.9}}),
        encoding="utf-8",
    )
    with patch("memory.memory_gate.GATED_STORE", gs):
        result = read_memory("found.key")
    assert result is not None
    assert result["value"] == "yes"


def test_list_memories_empty(tmp_path):
    with patch("memory.memory_gate.GATED_STORE", tmp_path / "empty.json"):
        entries = list_memories()
    assert entries == []


def test_list_memories_prefix_filter(tmp_path):
    gs = tmp_path / "gs.json"
    gs.write_text(
        json.dumps(
            {
                "foo.a": {"value": 1, "timestamp": "2026-01-01T00:00:00Z"},
                "bar.b": {"value": 2, "timestamp": "2026-01-02T00:00:00Z"},
            }
        ),
        encoding="utf-8",
    )
    with patch("memory.memory_gate.GATED_STORE", gs):
        results = list_memories(prefix="foo")
    assert len(results) == 1
    assert results[0]["key"] == "foo.a"


# ---------------------------------------------------------------------------
# SystemMemoryStore — basic schema + CRUD (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_schema_creates_tables(tmp_path):
    store = _make_store(tmp_path)
    rules = await store.get_governance_rules(active_only=False)
    # Seeded rules should be present.
    assert isinstance(rules, list)


@pytest.mark.asyncio
async def test_store_seeded_governance_rules(tmp_path):
    store = _make_store(tmp_path)
    rules = await store.get_governance_rules(active_only=True)
    names = {r.rule_name for r in rules}
    assert "FILE_SCOPE_ENFORCEMENT" in names
    assert "P3_SECRETS_BLOCKED" in names


@pytest.mark.asyncio
async def test_store_get_governance_rules_by_category(tmp_path):
    store = _make_store(tmp_path)
    rules = await store.get_governance_rules(category="file_scope")
    assert all(r.category == "file_scope" for r in rules)


@pytest.mark.asyncio
async def test_store_get_governance_rules_by_severity(tmp_path):
    store = _make_store(tmp_path)
    rules = await store.get_governance_rules(severity="critical")
    assert all(r.severity == "critical" for r in rules)


@pytest.mark.asyncio
async def test_store_get_rule_by_name(tmp_path):
    store = _make_store(tmp_path)
    rule = await store.get_rule_by_name("FILE_SCOPE_ENFORCEMENT")
    assert rule is not None
    assert rule.rule_name == "FILE_SCOPE_ENFORCEMENT"


@pytest.mark.asyncio
async def test_store_get_rule_by_name_missing(tmp_path):
    store = _make_store(tmp_path)
    rule = await store.get_rule_by_name("DOES_NOT_EXIST")
    assert rule is None


@pytest.mark.asyncio
async def test_store_insert_and_retrieve_learning(tmp_path):
    store = _make_store(tmp_path)
    lid = f"L-{uuid.uuid4().hex[:8]}"
    learning = Learning(
        id=lid,
        title="Test Learning",
        category="process",
        confidence="high",
        scope="repo-specific",
        content="Test content.",
        source="test_suite",
    )
    await store.insert_learning(learning)
    results = await store.get_learnings(limit=100)
    assert any(r.id == lid for r in results)


@pytest.mark.asyncio
async def test_store_learning_replace_on_same_id(tmp_path):
    store = _make_store(tmp_path)
    lid = f"L-{uuid.uuid4().hex[:8]}"
    base = Learning(
        id=lid,
        title="Original",
        category="process",
        confidence="low",
        scope="repo-specific",
        content="v1",
        source="s",
    )
    await store.insert_learning(base)
    updated = Learning(
        id=lid,
        title="Updated",
        category="process",
        confidence="high",
        scope="repo-specific",
        content="v2",
        source="s",
    )
    await store.insert_learning(updated)
    results = await store.get_learnings(limit=100)
    matching = [r for r in results if r.id == lid]
    assert len(matching) == 1
    assert matching[0].title == "Updated"


@pytest.mark.asyncio
async def test_store_get_learnings_by_scope(tmp_path):
    store = _make_store(tmp_path)
    lid = f"L-{uuid.uuid4().hex[:8]}"
    learning = Learning(
        id=lid,
        title="Cross-cutting learning",
        category="architecture",
        confidence="medium",
        scope="cross-cutting",
        content="Applies everywhere.",
        source="test_suite",
    )
    await store.insert_learning(learning)
    results = await store.get_learnings(scope="cross-cutting")
    assert any(r.id == lid for r in results)


@pytest.mark.asyncio
async def test_store_scope_violation_roundtrip(tmp_path):
    store = _make_store(tmp_path)
    vid = f"V-{uuid.uuid4().hex[:8]}"
    violation = ScopeViolation(
        id=vid,
        mission_id="M-TEST",
        task_id="T-TEST",
        expected_scope="05_FRONTEND_CONSOLE/",
        violated_files=["02_RUNTIME/bad.py"],
        detected_by="test_enforcer",
        resolution="pending",
        severity="warning",
    )
    await store.record_violation(violation)
    results = await store.get_violations(mission_id="M-TEST")
    assert len(results) == 1
    assert results[0].violated_files == ["02_RUNTIME/bad.py"]


@pytest.mark.asyncio
async def test_store_scope_violation_critical_filter(tmp_path):
    store = _make_store(tmp_path)
    vid = f"V-{uuid.uuid4().hex[:8]}"
    violation = ScopeViolation(
        id=vid,
        mission_id="M-CRIT",
        task_id="T-CRIT",
        expected_scope="02_RUNTIME/",
        violated_files=["05_FRONTEND_CONSOLE/bad.tsx"],
        detected_by="test",
        resolution="blocked",
        severity="critical",
    )
    await store.record_violation(violation)
    critical = await store.get_violations(severity="critical")
    assert any(r.id == vid for r in critical)


@pytest.mark.asyncio
async def test_store_session_lifecycle(tmp_path):
    store = _make_store(tmp_path)
    sid = await store.start_session("agent-test", {"repo": "chromatic-harness-v2"})
    assert sid
    await store.end_session(sid, "success", ["L-001"])


@pytest.mark.asyncio
async def test_store_assemble_context_structure(tmp_path):
    store = _make_store(tmp_path)
    ctx = await store.assemble_context()
    assert "governance_rules" in ctx
    assert "recent_learnings" in ctx
    assert "recent_scope_violations" in ctx
    assert "injected_at" in ctx


@pytest.mark.asyncio
async def test_store_assemble_context_p3_pulls_critical(tmp_path):
    store = _make_store(tmp_path)
    ctx = await store.assemble_context(privacy_class="P3")
    severities = {r["severity"] for r in ctx["governance_rules"]}
    # All rules should be critical for P3 class.
    assert severities <= {"critical"}


@pytest.mark.asyncio
async def test_store_assemble_context_include_rules_filter(tmp_path):
    store = _make_store(tmp_path)
    ctx = await store.assemble_context(include_rules=["FILE_SCOPE_ENFORCEMENT"])
    names = [r["name"] for r in ctx["governance_rules"]]
    assert "FILE_SCOPE_ENFORCEMENT" in names
    # Should only contain what we asked for.
    assert all(n == "FILE_SCOPE_ENFORCEMENT" for n in names)
