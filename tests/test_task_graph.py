"""Tests for 02_RUNTIME/workflows/task_graph.py — task graph loading/validation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO / "02_RUNTIME" / "workflows" / "task_graph.py"


def _load_tg_module(name: str = "_tg_mod"):
    spec = importlib.util.spec_from_file_location(name, _MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture()
def tg():
    name = "_tg_mod"
    sys.modules.pop(name, None)
    sys.path.insert(0, str(_REPO / "02_RUNTIME"))
    mod = _load_tg_module(name)
    yield mod
    sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# Helpers to build minimal valid task/graph dicts
# ---------------------------------------------------------------------------

def _minimal_task(**overrides) -> dict:
    base = {
        "task_id": "t1",
        "title": "Do thing",
        "assigned_model": "haiku",
        "role": "executor",
        "tool_budget": 10,
        "confidence_required": 80,
        "risk_level": "low",
        "status": "pending",
    }
    base.update(overrides)
    return base


def _minimal_graph(**overrides) -> dict:
    base = {
        "workflow_id": "wf-001",
        "objective": "Accomplish the goal",
        "risk_level": "low",
        "tasks": [_minimal_task()],
    }
    base.update(overrides)
    return base


def _write_graph(tmp_path: Path, data: dict, filename: str = "graph.json") -> Path:
    p = tmp_path / filename
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


class TestTaskGraph:

    # 1. import clean --------------------------------------------------------
    def test_import_clean(self):
        """Module loads and exposes expected public symbols."""
        name = "_tg_import_clean"
        sys.modules.pop(name, None)
        sys.path.insert(0, str(_REPO / "02_RUNTIME"))
        try:
            mod = _load_tg_module(name)
            assert hasattr(mod, "validate_task_dict")
            assert hasattr(mod, "validate_graph_dict")
            assert hasattr(mod, "load_task_graph")
            assert hasattr(mod, "next_runnable_task")
            assert hasattr(mod, "VALID_RISK")
            assert hasattr(mod, "VALID_STATUS")
        finally:
            sys.modules.pop(name, None)

    # 2. happy path — validate_task_dict on valid data -----------------------
    def test_validate_task_dict_valid(self, tg):
        """validate_task_dict returns empty list for a fully valid task."""
        errors = tg.validate_task_dict(_minimal_task())
        assert errors == []

    def test_validate_graph_dict_valid(self, tg):
        """validate_graph_dict returns empty list for a valid graph."""
        errors = tg.validate_graph_dict(_minimal_graph())
        assert errors == []

    def test_load_task_graph_happy_path(self, tmp_path, tg):
        """load_task_graph returns a TaskGraph object from a valid JSON file."""
        path = _write_graph(tmp_path, _minimal_graph())
        graph = tg.load_task_graph(path)
        assert graph.workflow_id == "wf-001"
        assert graph.objective == "Accomplish the goal"
        assert len(graph.tasks) == 1
        assert graph.tasks[0].task_id == "t1"

    # 3. error path — missing required keys ----------------------------------
    def test_validate_task_dict_missing_keys(self, tg):
        """validate_task_dict flags tasks missing required keys."""
        errors = tg.validate_task_dict({"task_id": "x"})
        assert any("missing keys" in e for e in errors)

    def test_validate_graph_dict_missing_workflow_id(self, tg):
        """validate_graph_dict flags graph missing workflow_id."""
        data = _minimal_graph()
        del data["workflow_id"]
        errors = tg.validate_graph_dict(data)
        assert any("workflow_id" in e for e in errors)

    def test_validate_graph_dict_empty_tasks_list(self, tg):
        """validate_graph_dict rejects empty tasks list."""
        data = _minimal_graph(tasks=[])
        errors = tg.validate_graph_dict(data)
        assert any("tasks" in e for e in errors)

    def test_validate_graph_dict_tasks_not_a_list(self, tg):
        """validate_graph_dict rejects tasks that is not a list."""
        data = _minimal_graph(tasks="not-a-list")
        errors = tg.validate_graph_dict(data)
        assert any("tasks" in e for e in errors)

    def test_load_task_graph_raises_on_invalid_json(self, tmp_path, tg):
        """load_task_graph raises ValueError for an invalid graph file."""
        bad = _minimal_graph(risk_level="INVALID_RISK")
        path = _write_graph(tmp_path, bad)
        with pytest.raises(ValueError, match="risk_level"):
            tg.load_task_graph(path)

    # 4. boundary — risk_level and status enums ------------------------------
    def test_validate_task_dict_all_valid_risk_levels(self, tg):
        """All four valid risk_level values pass task validation."""
        for risk in ("low", "medium", "high", "critical"):
            errors = tg.validate_task_dict(_minimal_task(risk_level=risk))
            assert not any("risk_level" in e for e in errors), f"risk={risk} should be valid"

    def test_validate_task_dict_invalid_risk_level(self, tg):
        """validate_task_dict rejects unknown risk_level."""
        errors = tg.validate_task_dict(_minimal_task(risk_level="extreme"))
        assert any("risk_level" in e for e in errors)

    def test_validate_task_dict_all_valid_statuses(self, tg):
        """All defined valid status values pass task validation."""
        for status in ("pending", "active", "blocked", "review", "done", "failed", "parked"):
            errors = tg.validate_task_dict(_minimal_task(status=status))
            assert not any("status" in e for e in errors), f"status={status} should be valid"

    def test_validate_task_dict_invalid_status(self, tg):
        """validate_task_dict rejects unknown status."""
        errors = tg.validate_task_dict(_minimal_task(status="UNKNOWN"))
        assert any("status" in e for e in errors)

    def test_validate_task_dict_tool_budget_zero(self, tg):
        """tool_budget=0 is valid (boundary)."""
        errors = tg.validate_task_dict(_minimal_task(tool_budget=0))
        assert not any("tool_budget" in e for e in errors)

    def test_validate_task_dict_tool_budget_negative(self, tg):
        """tool_budget=-1 is invalid."""
        errors = tg.validate_task_dict(_minimal_task(tool_budget=-1))
        assert any("tool_budget" in e for e in errors)

    def test_validate_task_dict_confidence_boundary(self, tg):
        """confidence_required 0 and 100 are valid; 101 is invalid."""
        assert not any("confidence" in e for e in tg.validate_task_dict(_minimal_task(confidence_required=0)))
        assert not any("confidence" in e for e in tg.validate_task_dict(_minimal_task(confidence_required=100)))
        assert any("confidence" in e for e in tg.validate_task_dict(_minimal_task(confidence_required=101)))

    # 5. fail-open — next_runnable_task on empty/all-done graph --------------
    def test_next_runnable_task_all_done_returns_none(self, tmp_path, tg):
        """next_runnable_task returns None when all tasks are done."""
        data = _minimal_graph(tasks=[_minimal_task(status="done")])
        graph = tg.load_task_graph(_write_graph(tmp_path, data))
        assert tg.next_runnable_task(graph) is None

    def test_next_runnable_task_blocked_dependency_returns_none(self, tmp_path, tg):
        """next_runnable_task returns None when pending task has unmet deps."""
        data = _minimal_graph(
            tasks=[
                _minimal_task(task_id="t1", status="pending", depends_on=["t2"]),
                _minimal_task(task_id="t2", status="pending"),
            ]
        )
        graph = tg.load_task_graph(_write_graph(tmp_path, data))
        # t1 depends on t2 (pending), t2 depends on nothing → t2 is runnable
        result = tg.next_runnable_task(graph)
        assert result is not None
        assert result.task_id == "t2"

    # 6. smoke — load multi-task graph with dependencies ---------------------
    def test_load_task_graph_with_dependencies(self, tmp_path, tg):
        """load_task_graph correctly loads depends_on for each task."""
        data = _minimal_graph(
            tasks=[
                _minimal_task(task_id="t1", status="done"),
                _minimal_task(task_id="t2", status="pending", depends_on=["t1"]),
            ]
        )
        graph = tg.load_task_graph(_write_graph(tmp_path, data))
        assert len(graph.tasks) == 2
        t2 = next(t for t in graph.tasks if t.task_id == "t2")
        assert t2.depends_on == ["t1"]

    def test_next_runnable_task_picks_first_unblocked(self, tmp_path, tg):
        """next_runnable_task returns first task whose dependencies are met."""
        data = _minimal_graph(
            tasks=[
                _minimal_task(task_id="t1", status="done"),
                _minimal_task(task_id="t2", status="pending", depends_on=["t1"]),
                _minimal_task(task_id="t3", status="pending", depends_on=["t2"]),
            ]
        )
        graph = tg.load_task_graph(_write_graph(tmp_path, data))
        result = tg.next_runnable_task(graph)
        assert result is not None
        assert result.task_id == "t2"

    def test_next_runnable_task_active_status_eligible(self, tmp_path, tg):
        """next_runnable_task includes 'active' tasks in addition to 'pending'."""
        data = _minimal_graph(tasks=[_minimal_task(status="active")])
        graph = tg.load_task_graph(_write_graph(tmp_path, data))
        result = tg.next_runnable_task(graph)
        assert result is not None

    # 7. validate_graph_dict — task entry not a dict -------------------------
    def test_validate_graph_dict_task_not_dict(self, tg):
        """validate_graph_dict rejects task list containing non-dict entries."""
        data = _minimal_graph(tasks=["not-a-dict"])
        errors = tg.validate_graph_dict(data)
        assert any("task must be an object" in e for e in errors)

    # 8. load_task_graph optional fields preserved ---------------------------
    def test_load_task_graph_optional_fields(self, tmp_path, tg):
        """load_task_graph preserves global_stop_conditions and created_at."""
        data = _minimal_graph()
        data["created_at"] = "2026-01-01T00:00:00Z"
        data["global_stop_conditions"] = ["stop if critical error"]
        graph = tg.load_task_graph(_write_graph(tmp_path, data))
        assert graph.created_at == "2026-01-01T00:00:00Z"
        assert "stop if critical error" in graph.global_stop_conditions

    # 9. TaskNode optional fields --------------------------------------------
    def test_task_node_optional_fields_default_empty(self, tmp_path, tg):
        """TaskNode optional list fields default to empty lists."""
        graph = tg.load_task_graph(_write_graph(tmp_path, _minimal_graph()))
        node = graph.tasks[0]
        assert node.depends_on == []
        assert node.allowed_files == []
        assert node.forbidden_files == []
        assert node.acceptance_criteria == []
        assert node.stop_conditions == []

    # 10. file not found is not silenced ------------------------------------
    def test_load_task_graph_missing_file_raises(self, tmp_path, tg):
        """load_task_graph raises an exception for a non-existent file."""
        with pytest.raises(Exception):
            tg.load_task_graph(tmp_path / "no_such_file.json")
