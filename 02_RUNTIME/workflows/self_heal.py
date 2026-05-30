"""Self-heal band: confidence 50–69 triggers GO DEEP + task-graph re-decomposition."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from workflows.models import ConfidenceRecord, WorkflowDecision
from workflows.roles import build_standard_pipeline, write_active_graph

SELF_HEAL_MIN = 50.0
SELF_HEAL_MAX = 69.0


def in_self_heal_band(score: float) -> bool:
    return SELF_HEAL_MIN <= score <= SELF_HEAL_MAX


def needs_self_heal(record: ConfidenceRecord) -> bool:
    """True when GO should auto-decompose instead of stopping at plan_only."""
    return (
        record.workflow_decision == WorkflowDecision.PLAN_ONLY
        and in_self_heal_band(record.confidence_score)
    )


def enqueue_graph_subtasks(
    graph: dict[str, Any],
    *,
    bead_id: str = "",
    parent_score: float = 0.0,
) -> list[str]:
    """Enqueue scout/build follow-ups from a decomposed graph into intake_queue."""
    import sys

    _runtime = Path(__file__).resolve().parents[1]
    if str(_runtime) not in sys.path:
        sys.path.insert(0, str(_runtime))

    from intake.queue import append_entry  # noqa: E402

    ids: list[str] = []
    wf_id = graph.get("workflow_id", "WF-self-heal")
    for task in graph.get("tasks", []):
        role = task.get("role", "")
        if role not in ("scout", "worker"):
            continue
        tid = task.get("task_id", "sub")
        entry_id = f"sh-{wf_id}-{tid}"[:80]
        append_entry(
            {
                "id": entry_id,
                "source": "workflow",
                "kind": "follow_up",
                "status": "queued",
                "title": (task.get("title") or tid)[:120],
                "goal": task.get("title") or tid,
                "priority": "P2",
                "type": "task",
                "tier": 2,
                "lane": "agent",
                "bead_id": bead_id,
                "context": {
                    "self_heal": True,
                    "workflow_id": wf_id,
                    "task_id": tid,
                    "role": role,
                    "parent_confidence": parent_score,
                },
            }
        )
        ids.append(entry_id)
    return ids


def apply_self_heal(
    repo_root: Path,
    bead: dict[str, str],
    record: ConfidenceRecord,
) -> dict[str, Any]:
    """Build task graph, write active-graph.json, enqueue decomposed subtasks."""
    objective = bead.get("title") or "Re-decompose blocked task"
    bead_id = bead.get("bead_id", "")
    graph = build_standard_pipeline(objective, bead_id=bead_id)
    graph_path = write_active_graph(graph, repo_root=repo_root)
    intake_ids = enqueue_graph_subtasks(
        graph,
        bead_id=bead_id,
        parent_score=record.confidence_score,
    )
    return {
        "self_heal": True,
        "band": f"{int(SELF_HEAL_MIN)}-{int(SELF_HEAL_MAX)}",
        "task_graph_path": str(graph_path.relative_to(repo_root)),
        "tasks": [t["task_id"] for t in graph["tasks"]],
        "intake_enqueued": intake_ids,
        "cmp_decision": record.cmp_decision,
    }
