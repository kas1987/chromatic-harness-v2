"""Task graph loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workflows.models import TaskGraph, TaskNode

REQUIRED_GRAPH_KEYS = {"workflow_id", "objective", "risk_level", "tasks"}
REQUIRED_TASK_KEYS = {
    "task_id",
    "title",
    "assigned_model",
    "role",
    "tool_budget",
    "confidence_required",
    "risk_level",
    "status",
}
VALID_RISK = {"low", "medium", "high", "critical"}
VALID_STATUS = {"pending", "active", "blocked", "review", "done", "failed", "parked"}


def validate_task_dict(task: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_TASK_KEYS - set(task)
    if missing:
        errors.append(f"task {task.get('task_id', '?')}: missing keys {sorted(missing)}")
    if task.get("risk_level") not in VALID_RISK:
        errors.append(f"task {task.get('task_id', '?')}: invalid risk_level")
    if task.get("status") not in VALID_STATUS:
        errors.append(f"task {task.get('task_id', '?')}: invalid status")
    budget = task.get("tool_budget")
    if budget is not None and (not isinstance(budget, int) or budget < 0):
        errors.append(f"task {task.get('task_id', '?')}: tool_budget must be >= 0")
    conf = task.get("confidence_required")
    if conf is not None and (not isinstance(conf, int) or conf < 0 or conf > 100):
        errors.append(f"task {task.get('task_id', '?')}: confidence_required out of range")
    return errors


def validate_graph_dict(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_GRAPH_KEYS - set(data)
    if missing:
        errors.append(f"graph missing keys: {sorted(missing)}")
    if data.get("risk_level") not in VALID_RISK:
        errors.append("graph: invalid risk_level")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("graph: tasks must be a non-empty list")
    elif isinstance(tasks, list):
        for task in tasks:
            if isinstance(task, dict):
                errors.extend(validate_task_dict(task))
            else:
                errors.append("graph: each task must be an object")
    return errors


def load_task_graph(path: Path) -> TaskGraph:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_graph_dict(data)
    if errors:
        raise ValueError("; ".join(errors))
    return TaskGraph.from_dict(data)


def next_runnable_task(graph: TaskGraph) -> TaskNode | None:
    done = {t.task_id for t in graph.tasks if t.status == "done"}
    for task in graph.tasks:
        if task.status not in ("pending", "active"):
            continue
        if all(dep in done for dep in task.depends_on):
            return task
    return None
