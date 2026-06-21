"""Tests for 02_RUNTIME/intake/queue.py — intake queue module."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading via importlib so path constants can be observed/overridden
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO / "02_RUNTIME" / "intake" / "queue.py"


def _load_queue_module(name: str = "intake_queue_mod"):
    """Load intake/queue.py as a standalone module."""
    spec = importlib.util.spec_from_file_location(name, _MODULE_PATH)
    assert spec is not None and spec.loader is not None, "spec must be loadable"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture()
def qmod():
    """Return the queue module, evicting cached copy each test."""
    name = "intake_queue_mod"
    sys.modules.pop(name, None)
    mod = _load_queue_module(name)
    yield mod
    sys.modules.pop(name, None)


# ---------------------------------------------------------------------------

class TestQueue:

    # 1. import clean --------------------------------------------------------
    def test_import_clean(self):
        """Module loads without errors and exports expected symbols."""
        mod = _load_queue_module("_tq_import_clean")
        try:
            assert hasattr(mod, "append_entry")
            assert hasattr(mod, "list_entries")
            assert hasattr(mod, "list_queued")
            assert hasattr(mod, "iter_queued")
            assert hasattr(mod, "record_status")
            assert hasattr(mod, "validate_entry")
            assert hasattr(mod, "normalize_entry")
            assert hasattr(mod, "IntakeEntry")
        finally:
            sys.modules.pop("_tq_import_clean", None)

    # 2. happy path — append and retrieve ------------------------------------
    def test_append_and_list_entries(self, tmp_path, qmod):
        """append_entry writes a line; list_entries reads it back."""
        q_file = tmp_path / "intake_queue.jsonl"
        entry = qmod.append_entry(
            {
                "source": "manual",
                "kind": "goal",
                "title": "do something",
                "goal": "accomplish the objective",
            },
            path=q_file,
        )
        assert entry.source == "manual"
        assert entry.kind == "goal"
        assert entry.status == "queued"
        entries = qmod.list_entries(path=q_file)
        assert len(entries) == 1
        assert entries[0].title == "do something"

    # 3. validate_entry — error path -----------------------------------------
    def test_validate_entry_missing_required_fields(self, qmod):
        """validate_entry returns errors for empty/missing required fields."""
        errors = qmod.validate_entry({})
        required = {"id", "source", "kind", "status", "title", "queued_at"}
        error_text = " ".join(errors)
        for field in required:
            assert field in error_text, f"expected error for {field}"

    def test_validate_entry_invalid_source(self, qmod):
        """validate_entry rejects unknown source values."""
        data = {
            "id": "x",
            "source": "BADVALUE",
            "kind": "goal",
            "status": "queued",
            "title": "t",
            "queued_at": "2026-01-01T00:00:00Z",
            "priority": "P2",
            "tier": 3,
            "type": "task",
            "goal": "g",
        }
        errors = qmod.validate_entry(data)
        assert any("source" in e for e in errors)

    def test_validate_entry_invalid_kind(self, qmod):
        """validate_entry rejects unknown kind values."""
        data = {
            "id": "x",
            "source": "manual",
            "kind": "NOTAKIND",
            "status": "queued",
            "title": "t",
            "queued_at": "2026-01-01T00:00:00Z",
            "priority": "P2",
            "tier": 3,
            "type": "task",
        }
        errors = qmod.validate_entry(data)
        assert any("kind" in e for e in errors)

    def test_validate_entry_invalid_tier(self, qmod):
        """validate_entry rejects tier values outside 0-4."""
        data = {
            "id": "x",
            "source": "manual",
            "kind": "follow_up",
            "status": "queued",
            "title": "t",
            "queued_at": "2026-01-01T00:00:00Z",
            "tier": 99,
        }
        errors = qmod.validate_entry(data)
        assert any("tier" in e for e in errors)

    def test_validate_entry_goal_without_goal_field(self, qmod):
        """kind=goal requires a non-empty goal field."""
        data = {
            "id": "x",
            "source": "manual",
            "kind": "goal",
            "status": "queued",
            "title": "t",
            "queued_at": "2026-01-01T00:00:00Z",
        }
        errors = qmod.validate_entry(data)
        assert any("goal" in e for e in errors)

    # 4. boundary — tier edge values -----------------------------------------
    def test_validate_entry_tier_boundary_values(self, qmod):
        """tier values 0 and 4 are valid; tier=-1 and tier=5 are not."""
        base = {
            "id": "x",
            "source": "manual",
            "kind": "follow_up",
            "status": "queued",
            "title": "t",
            "queued_at": "2026-01-01T00:00:00Z",
        }
        assert not any("tier" in e for e in qmod.validate_entry({**base, "tier": 0}))
        assert not any("tier" in e for e in qmod.validate_entry({**base, "tier": 4}))
        assert any("tier" in e for e in qmod.validate_entry({**base, "tier": -1}))
        assert any("tier" in e for e in qmod.validate_entry({**base, "tier": 5}))

    # 5. fail-open — empty / missing file ------------------------------------
    def test_list_entries_missing_file_returns_empty(self, tmp_path, qmod):
        """list_entries returns [] when the queue file does not exist."""
        result = qmod.list_entries(path=tmp_path / "nonexistent.jsonl")
        assert result == []

    def test_list_queued_empty_file(self, tmp_path, qmod):
        """list_queued returns [] when queue file is empty."""
        q_file = tmp_path / "intake_queue.jsonl"
        q_file.write_text("", encoding="utf-8")
        assert qmod.list_queued(path=q_file) == []

    # 6. smoke — normalize_entry defaults ------------------------------------
    def test_normalize_entry_sets_defaults(self, qmod):
        """normalize_entry fills status, priority, type, tier when absent."""
        out = qmod.normalize_entry({"source": "manual", "kind": "follow_up", "title": "x"})
        assert out["status"] == "queued"
        assert out["priority"] == "P2"
        assert out["type"] == "task"
        assert out["tier"] == 3
        assert out["id"].startswith("intake-")

    def test_normalize_entry_bead_dispatch_sets_bead_id(self, qmod):
        """normalize_entry sets bead_id from id for bead_dispatch kind."""
        out = qmod.normalize_entry(
            {"source": "bead_hook", "kind": "bead_dispatch", "title": "x", "id": "abc"}
        )
        assert out["bead_id"] == "abc"

    # 7. record_status appends transition entry ------------------------------
    def test_record_status_appends_status_change(self, tmp_path, qmod):
        """record_status appends a new line with updated status."""
        q_file = tmp_path / "intake_queue.jsonl"
        entry = qmod.append_entry(
            {
                "source": "inbox",
                "kind": "follow_up",
                "title": "follow this up",
            },
            path=q_file,
        )
        updated = qmod.record_status(entry, "processed", path=q_file)
        assert updated.status == "processed"
        # Two lines in the file (original + status transition)
        lines = [l for l in q_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 2

    # 8. list_queued deduplicates by id, keeps last status -------------------
    def test_list_queued_deduplicates(self, tmp_path, qmod):
        """list_queued returns latest status per id — processed entries excluded."""
        q_file = tmp_path / "intake_queue.jsonl"
        entry = qmod.append_entry(
            {
                "source": "manual",
                "kind": "follow_up",
                "title": "dedup me",
            },
            path=q_file,
        )
        # Mark as processed
        qmod.record_status(entry, "processed", path=q_file)
        queued = qmod.list_queued(path=q_file)
        assert queued == []

    # 9. IntakeEntry round-trip via to_dict / from_dict ----------------------
    def test_intake_entry_roundtrip(self, qmod):
        """IntakeEntry.to_dict() -> from_dict() preserves all fields."""
        original = qmod.IntakeEntry(
            id="test-123",
            source="manual",
            kind="goal",
            status="queued",
            title="my goal",
            queued_at="2026-01-01T00:00:00Z",
            goal="accomplish something",
            priority="P1",
            type="epic",
            tier=2,
            bead_id="b-456",
            lane="agent",
            context={"key": "val"},
        )
        restored = qmod.IntakeEntry.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.goal == original.goal
        assert restored.lane == original.lane
        assert restored.context == original.context
        assert restored.tier == original.tier

    # 10. append_entry raises ValueError on bad data -------------------------
    def test_append_entry_raises_on_invalid_source(self, tmp_path, qmod):
        """append_entry raises ValueError when source is invalid."""
        with pytest.raises(ValueError, match="source"):
            qmod.append_entry(
                {
                    "source": "INVALID",
                    "kind": "follow_up",
                    "title": "bad",
                },
                path=tmp_path / "q.jsonl",
            )

    # 11. iter_queued yields same as list_queued -----------------------------
    def test_iter_queued_matches_list_queued(self, tmp_path, qmod):
        """iter_queued yields identical results to list_queued."""
        q_file = tmp_path / "intake_queue.jsonl"
        qmod.append_entry(
            {"source": "agent_lead", "kind": "follow_up", "title": "a"},
            path=q_file,
        )
        qmod.append_entry(
            {"source": "inbox", "kind": "follow_up", "title": "b"},
            path=q_file,
        )
        from_list = qmod.list_queued(path=q_file)
        from_iter = list(qmod.iter_queued(path=q_file))
        assert [e.id for e in from_list] == [e.id for e in from_iter]

    # 12. JSONL persistence integrity ----------------------------------------
    def test_queue_file_is_valid_jsonl(self, tmp_path, qmod):
        """Each line in the queue file is valid JSON."""
        q_file = tmp_path / "intake_queue.jsonl"
        for i in range(3):
            qmod.append_entry(
                {"source": "manual", "kind": "follow_up", "title": f"item {i}"},
                path=q_file,
            )
        for line in q_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                obj = json.loads(line)  # must not raise
                assert "id" in obj and "status" in obj
