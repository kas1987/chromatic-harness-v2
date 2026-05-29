"""Enqueue follow-up goals from session closure into the intake queue."""

from __future__ import annotations

import re
from typing import Any

from intake.queue import append_entry

_SKIP = re.compile(r"^[\s—\-]+$|^\(see git log\)$", re.I)


def enqueue_session_follow_ups(
    goals: list[str],
    *,
    mission_id: str = "",
    priority: str = "P2",
    context: dict[str, Any] | None = None,
) -> list[str]:
    """Append follow_up entries for each non-empty next-session goal. Returns entry ids."""
    ids: list[str] = []
    base_ctx = dict(context or {})
    if mission_id:
        base_ctx["parent_mission"] = mission_id

    for idx, raw in enumerate(goals):
        goal = (raw or "").strip()
        if not goal or _SKIP.match(goal):
            continue
        entry_id = f"fu-{mission_id or 'session'}-{idx}"
        append_entry(
            {
                "id": entry_id,
                "source": "closure",
                "kind": "follow_up",
                "status": "queued",
                "title": goal[:120],
                "goal": goal,
                "priority": priority,
                "type": "task",
                "tier": 2,
                "context": base_ctx,
            }
        )
        ids.append(entry_id)
    return ids
