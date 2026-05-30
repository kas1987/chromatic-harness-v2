"""Harness event JSONL emitter conforming to schemas/harness_event.schema.json."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "00_SOURCE_OF_TRUTH").exists() or (parent / ".git").exists():
            return parent
    return Path.cwd()


_VALID_EVENT_TYPES = frozenset(
    {
        "observe",
        "classify",
        "score",
        "dispatch",
        "execute",
        "validate",
        "record",
        "halt",
        "incident",
    }
)
_VALID_RISK_LEVELS = frozenset({"low", "medium", "high", "critical", "unknown"})
_VALID_RESULTS = frozenset({"passed", "failed", "blocked", "halted", "partial"})


def emit_harness_event(
    event_type: str,
    task_id: str,
    agent: str,
    model: str,
    confidence_score: float,
    risk_level: str,
    files_touched: list[str],
    tools_used: list[str],
    result: str,
    *,
    notes: str | None = None,
    duration_ms: int | None = None,
    repo_root: Path | None = None,
) -> None:
    """Append a harness event as a JSONL line to 07_LOGS_AND_AUDIT/harness_events.jsonl.

    All required fields from harness_event.schema.json are included.
    Raises ValueError for invalid enum values so callers catch schema violations early.
    """
    if event_type not in _VALID_EVENT_TYPES:
        raise ValueError(
            f"Invalid event_type {event_type!r}. Must be one of {sorted(_VALID_EVENT_TYPES)}"
        )
    if risk_level not in _VALID_RISK_LEVELS:
        raise ValueError(
            f"Invalid risk_level {risk_level!r}. Must be one of {sorted(_VALID_RISK_LEVELS)}"
        )
    if result not in _VALID_RESULTS:
        raise ValueError(
            f"Invalid result {result!r}. Must be one of {sorted(_VALID_RESULTS)}"
        )
    if not (0 <= confidence_score <= 100):
        raise ValueError(
            f"confidence_score must be between 0 and 100, got {confidence_score}"
        )

    root = repo_root or _repo_root()
    log_dir = root / "07_LOGS_AND_AUDIT"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "harness_events.jsonl"

    event: dict = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "task_id": task_id,
        "agent": agent,
        "model": model,
        "confidence_score": confidence_score,
        "risk_level": risk_level,
        "files_touched": list(files_touched),
        "tools_used": list(tools_used),
        "result": result,
    }
    if notes is not None:
        event["notes"] = notes
    if duration_ms is not None:
        event["duration_ms"] = int(duration_ms)

    line = json.dumps(event, ensure_ascii=False)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
