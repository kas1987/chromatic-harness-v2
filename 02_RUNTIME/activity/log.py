"""Unified activity logging: workflow run log + two-log + optional intake."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from activity.lanes import normalize_lane

_USAGE_LOG_ENV = "CHROMATIC_LEARNING_USAGE_LOG"


def _usage_log_path(repo_root: Path) -> Path:
    import os

    override = os.environ.get(_USAGE_LOG_ENV, "").strip()
    if override:
        return Path(override).resolve()
    return repo_root / ".agents" / "metrics" / "learning_usage.jsonl"


def _load_seen_ikeys(log_path: Path) -> set[str]:
    seen: set[str] = set()
    if not log_path.is_file():
        return seen
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        key = str(row.get("idempotency_key") or "")
        if key:
            seen.add(key)
    return seen


def emit_learning_outcome(
    repo_root: Path,
    *,
    learning_name: str,
    outcome: str,
    rig_id: str = "",
    error_category: str = "",
    timestamp_utc: str = "",
) -> bool:
    """Append one applied_success or applied_failure event to the learning usage log.

    Returns True if emitted, False if skipped (duplicate or invalid input).
    outcome must be 'applied_success' or 'applied_failure'.
    """
    if outcome not in ("applied_success", "applied_failure"):
        return False
    name = learning_name.strip()
    if not name:
        return False

    ts = timestamp_utc.strip() or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    raw_key = f"{name}|{outcome}|{rig_id}|{ts}"
    ikey = hashlib.sha1(raw_key.encode()).hexdigest()[:16]

    log_path = _usage_log_path(repo_root)
    seen = _load_seen_ikeys(log_path)
    if ikey in seen:
        return False

    event: dict[str, Any] = {
        "timestamp_utc": ts,
        "event_type": outcome,
        "learning_name": name,
        "learning_path": f".agents/learnings/{name}.md",
        "idempotency_key": ikey,
        "notes": "workflow_execution",
    }
    if rig_id:
        event["rig_id"] = rig_id
    if error_category and outcome == "applied_failure":
        event["error_category"] = error_category

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=True) + "\n")
    return True


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
    applied_learning: str = "",
    error_category: str = "",
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

    if applied_learning.strip():
        outcome = "applied_failure" if error else "applied_success"
        emit_learning_outcome(
            repo_root,
            learning_name=applied_learning.strip(),
            outcome=outcome,
            rig_id=bead_id,
            error_category=error_category,
        )

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
