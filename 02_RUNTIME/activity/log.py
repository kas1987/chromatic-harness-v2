"""Unified activity logging: workflow run log + two-log + optional intake."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from activity.lanes import normalize_lane


@dataclass
class ActivityLogResult:
    workflow_log_path: str
    intake_entry_id: str = ""
    intake_queued: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_log_path": self.workflow_log_path,
            "intake_entry_id": self.intake_entry_id,
            "intake_queued": self.intake_queued,
        }


def _event_to_mode(event_type: str) -> str:
    if event_type.startswith("workflow."):
        return event_type.replace("workflow.", "").replace("_", " ").upper()
    return event_type.replace(".", " ").upper()


def _should_enqueue_intake(
    *,
    lane: str,
    error: str,
    intake_on_failure: bool,
) -> bool:
    if intake_on_failure and error.strip():
        return True
    if lane == "human" and error.strip():
        return True
    return False


def log_activity(
    repo_root: Path,
    *,
    event_type: str,
    bead_id: str = "",
    lane: str = "agent",
    decision: str = "",
    summary: str = "",
    error: str = "",
    handoff: dict[str, Any] | None = None,
    confidence: dict[str, Any] | None = None,
    agent_role: str = "orchestrator",
    lock_owner: str = "",
    intake_on_failure: bool = False,
    intake_context: dict[str, Any] | None = None,
    enqueue_intake: bool = False,
) -> ActivityLogResult:
    """Append workflow + two-log; optionally enqueue intake follow_up."""
    import sys

    runtime = Path(__file__).resolve().parents[1]
    if str(runtime) not in sys.path:
        sys.path.insert(0, str(runtime))

    from workflows.run_log import append_run_log  # noqa: E402

    resolved_lane = normalize_lane(lane)
    mode = _event_to_mode(event_type)
    payload: dict[str, Any] = {
        "mode": mode,
        "event_type": event_type,
        "bead_id": bead_id,
        "decision": decision or ("failed" if error else "ok"),
        "agent_role": agent_role,
        "lane": resolved_lane,
        "summary": summary[:2000] if summary else "",
        "handoff": handoff or {},
    }
    if lock_owner:
        payload["lock_owner"] = lock_owner
    if error:
        payload["error"] = error[:4000]
    if confidence:
        payload["confidence"] = confidence

    log_path = append_run_log(repo_root, payload)
    result = ActivityLogResult(workflow_log_path=str(log_path))

    do_intake = enqueue_intake or _should_enqueue_intake(
        lane=resolved_lane,
        error=error,
        intake_on_failure=intake_on_failure,
    )
    if not do_intake:
        return result

    from intake.queue import append_entry  # noqa: E402

    ctx = dict(intake_context or {})
    ctx.setdefault("event_type", event_type)
    if error:
        ctx.setdefault("error", error[:2000])
    if summary:
        ctx.setdefault("summary", summary[:500])
    if lock_owner:
        ctx.setdefault("lock_owner", lock_owner)

    title = summary[:120] if summary else f"Activity follow-up: {event_type}"
    if error and len(title) < 40:
        title = (error.splitlines()[0] or title)[:120]

    entry_id = f"act-{uuid.uuid4().hex[:12]}"
    entry = append_entry(
        {
            "id": entry_id,
            "source": "workflow",
            "kind": "follow_up",
            "status": "queued",
            "title": title,
            "goal": summary or error or title,
            "priority": "P1" if resolved_lane == "human" else "P2",
            "type": "task",
            "tier": 2,
            "lane": resolved_lane,
            "bead_id": bead_id,
            "context": ctx,
        },
        repo_root=repo_root,
    )
    result.intake_entry_id = entry.id
    result.intake_queued = True
    return result
