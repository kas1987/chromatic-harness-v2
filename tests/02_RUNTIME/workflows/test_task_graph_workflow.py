"""Tests for workflows.task_graph — validation, loading, and next-task logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflows.models import TaskGraph, TaskNode
from workflows.task_graph import (
    REQUIRED_GRAPH_KEYS,
    REQUIRED_TASK_KEYS,
    VALID_RISK,
    VALID_STATUS,
    load_task_graph,
    next_runnable_task,
    validate_graph_dict,
    validate_task_dict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_task(**overrides) -> dict:
    t = {
        "task_id": "t-1",
        "title": "Do something",
        "assigned_model": "sonnet",
        "role": "worker",
        "tool_budget": 20,
        "confidence_required": 75,
        "risk_level": "low",
        "status": "pending",
    }
    t.update(overrides)
    return t


def _minimal_graph(**overrides) -> dict:
    g = {
        "workflow_id": "WF-001",
        "objective": "Test objective",
        "risk_level": "low",
        "tasks": [_minimal_task()],
    }
    g.update(overrides)
    return g


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_required_graph_keys(self):
        assert {"workflow_id", "objective", "risk_level", "tasks"} == REQUIRED_GRAPH_KEYS

    def test_valid_risk_levels(self):
        assert VALID_RISK == {"low", "medium", "high", "critical"}

    def test_valid_status_values(self):
        assert "pending" in VALID_STATUS
        assert "done" in VALID_STATUS
        assert "failed" in VALID_STATUS


# ---------------------------------------------------------------------------
# validate_task_dict
# ---------------------------------------------------------------------------


class TestValidateTaskDict:
    def test_valid_task_returns_no_errors(self):
        assert validate_task_dict(_minimal_task()) == []

    def test_missing_key_reported(self):
        task = _minimal_task()
        del task["title"]
        errors = validate_task_dict(task)
        assert any("title" in e for e in errors)

    def test_invalid_risk_level_reported(self):
        errors = validate_task_dict(_minimal_task(risk_level="unknown"))
        assert any("risk_level" in e for e in errors)

    def test_invalid_status_reported(self):
        errors = validate_task_dict(_minimal_task(status="mystery"))
        assert any("status" in e for e in errors)

    def test_negative_tool_budget_reported(self):
        errors = validate_task_dict(_minimal_task(tool_budget=-1))
        assert any("tool_budget" in e for e in errors)

    def test_zero_tool_budget_allowed(self):
        assert validate_task_dict(_minimal_task(tool_budget=0)) == []

    def test_confidence_out_of_range_high(self):
        errors = validate_task_dict(_minimal_task(confidence_required=101))
        assert any("confidence_required" in e for e in errors)

    def test_confidence_out_of_range_low(self):
        errors = validate_task_dict(_minimal_task(confidence_required=-1))
        assert any("confidence_required" in e for e in errors)

    def test_confidence_at_boundary_ok(self):
        assert validate_task_dict(_minimal_task(confidence_required=0)) == []
        assert validate_task_dict(_minimal_task(confidence_required=100)) == []

    def test_non_int_tool_budget_reported(self):
        errors = validate_task_dict(_minimal_task(tool_budget="twenty"))
        assert any("tool_budget" in e for e in errors)

    def test_all_valid_status_values_accepted(self):
        for status in VALID_STATUS:
            errors = validate_task_dict(_minimal_task(status=status))
            status_errors = [e for e in errors if "status" in e]
            assert status_errors == [], f"status '{status}' should be valid"

    def test_all_valid_risk_levels_accepted(self):
        for risk in VALID_RISK:
            errors = validate_task_dict(_minimal_task(risk_level=risk))
            risk_errors = [e for e in errors if "risk_level" in e]
            assert risk_errors == [], f"risk_level '{risk}' should be valid"


# ---------------------------------------------------------------------------
# validate_graph_dict
# ---------------------------------------------------------------------------


class TestValidateGraphDict:
    def test_valid_graph_returns_no_errors(self):
        assert validate_graph_dict(_minimal_graph()) == []

    def test_missing_workflow_id_reported(self):
        g = _minimal_graph()
        del g["workflow_id"]
        errors = validate_graph_dict(g)
        assert any("workflow_id" in e for e in errors)

    def test_missing_objective_reported(self):
        g = _minimal_graph()
        del g["objective"]
        errors = validate_graph_dict(g)
        assert any("objective" in e for e in errors)

    def test_invalid_risk_level_reported(self):
        errors = validate_graph_dict(_minimal_graph(risk_level="extreme"))
        assert any("risk_level" in e for e in errors)

    def test_empty_tasks_reported(self):
        errors = validate_graph_dict(_minimal_graph(tasks=[]))
        assert any("tasks" in e for e in errors)

    def test_non_list_tasks_reported(self):
        errors = validate_graph_dict(_minimal_graph(tasks="not_a_list"))
        assert any("tasks" in e for e in errors)

    def test_invalid_task_propagated(self):
        task = _minimal_task(status="bad_status")
        errors = validate_graph_dict(_minimal_graph(tasks=[task]))
        assert len(errors) > 0

    def test_non_dict_task_reported(self):
        errors = validate_graph_dict(_minimal_graph(tasks=["not_a_dict"]))
        assert any("object" in e for e in errors)

    def test_multiple_tasks_all_validated(self):
        tasks = [
            _minimal_task(task_id="t-1"),
            _minimal_task(task_id="t-2", status="invalid_status"),
        ]
        errors = validate_graph_dict(_minimal_graph(tasks=tasks))
        assert any("t-2" in e for e in errors)


# ---------------------------------------------------------------------------
# load_task_graph
# ---------------------------------------------------------------------------


class TestLoadTaskGraph:
    def test_loads_valid_json(self, tmp_path):
        path = tmp_path / "graph.json"
        path.write_text(json.dumps(_minimal_graph()), encoding="utf-8")
        graph = load_task_graph(path)
        assert isinstance(graph, TaskGraph)
        assert graph.workflow_id == "WF-001"

    def test_raises_on_invalid_graph(self, tmp_path):
        bad = _minimal_graph(risk_level="extreme")
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(ValueError):
            load_task_graph(path)

    def test_loads_task_nodes(self, tmp_path):
        path = tmp_path / "graph.json"
        path.write_text(json.dumps(_minimal_graph()), encoding="utf-8")
        graph = load_task_graph(path)
        assert len(graph.tasks) == 1
        assert isinstance(graph.tasks[0], TaskNode)

    def test_multi_task_graph(self, tmp_path):
        tasks = [
            _minimal_task(task_id="t-1"),
            _minimal_task(task_id="t-2", depends_on=["t-1"]),
        ]
        g = _minimal_graph(tasks=tasks)
        path = tmp_path / "graph.json"
        path.write_text(json.dumps(g), encoding="utf-8")
        graph = load_task_graph(path)
        assert len(graph.tasks) == 2


# ---------------------------------------------------------------------------
# next_runnable_task
# ---------------------------------------------------------------------------


class TestNextRunnableTask:
    def _make_graph(self, tasks: list[dict]) -> TaskGraph:
        return TaskGraph.from_dict(_minimal_graph(tasks=tasks))

    def test_returns_first_pending_task_with_no_deps(self):
        graph = self._make_graph([_minimal_task(task_id="t-1", status="pending")])
        task = next_runnable_task(graph)
        assert task is not None
        assert task.task_id == "t-1"

    def test_returns_active_task(self):
        graph = self._make_graph([_minimal_task(task_id="t-1", status="active")])
        task = next_runnable_task(graph)
        assert task is not None
        assert task.task_id == "t-1"

    def test_skips_done_task(self):
        graph = self._make_graph([_minimal_task(task_id="t-1", status="done")])
        task = next_runnable_task(graph)
        assert task is None

    def test_skips_failed_task(self):
        graph = self._make_graph([_minimal_task(task_id="t-1", status="failed")])
        task = next_runnable_task(graph)
        assert task is None

    def test_skips_blocked_task(self):
        graph = self._make_graph([_minimal_task(task_id="t-1", status="blocked")])
        task = next_runnable_task(graph)
        assert task is None

    def test_dep_not_done_blocks_task(self):
        tasks = [
            _minimal_task(task_id="t-1", status="pending"),
            {**_minimal_task(task_id="t-2", status="pending"), "depends_on": ["t-1"]},
        ]
        graph = self._make_graph(tasks)
        task = next_runnable_task(graph)
        # Only t-1 is runnable (t-2 depends on t-1)
        assert task.task_id == "t-1"

    def test_dep_done_unblocks_task(self):
        tasks = [
            _minimal_task(task_id="t-1", status="done"),
            {**_minimal_task(task_id="t-2", status="pending"), "depends_on": ["t-1"]},
        ]
        graph = self._make_graph(tasks)
        task = next_runnable_task(graph)
        assert task.task_id == "t-2"

    def test_returns_none_when_all_done(self):
        tasks = [
            _minimal_task(task_id="t-1", status="done"),
            _minimal_task(task_id="t-2", status="done"),
        ]
        graph = self._make_graph(tasks)
        assert next_runnable_task(graph) is None

    def test_returns_none_on_empty_tasks(self):
        # Build the TaskGraph directly since load_task_graph rejects empty tasks
        graph = TaskGraph(
            workflow_id="WF-empty",
            objective="x",
            risk_level="low",
            tasks=[],
        )
        assert next_runnable_task(graph) is None

    def test_chain_of_deps_returns_first_runnable(self):
        tasks = [
            _minimal_task(task_id="t-1", status="done"),
            {**_minimal_task(task_id="t-2", status="done"), "depends_on": ["t-1"]},
            {**_minimal_task(task_id="t-3", status="pending"), "depends_on": ["t-2"]},
        ]
        graph = self._make_graph(tasks)
        task = next_runnable_task(graph)
        assert task.task_id == "t-3"
