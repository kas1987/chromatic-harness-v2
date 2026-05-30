"""Append-only intake queue for goals, bead dispatch, and follow-ups."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE = REPO_ROOT / "07_LOGS_AND_AUDIT" / "intake_queue.jsonl"

VALID_SOURCES = frozenset(
    {"bead_hook", "closure", "inbox", "manual", "goal", "workflow"}
)
VALID_KINDS = frozenset({"bead_dispatch", "goal", "follow_up"})
VALID_STATUS = frozenset({"queued", "processing", "processed", "failed", "skipped"})
VALID_PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})
VALID_TYPES = frozenset({"task", "bug", "epic", "chore"})
VALID_LANES = frozenset({"agent", "human", "review"})


@dataclass
class IntakeEntry:
    id: str
    source: str
    kind: str
    status: str
    title: str
    queued_at: str
    goal: str = ""
    priority: str = "P2"
    type: str = "task"
    tier: int = 3
    bead_id: str = ""
    lane: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    processed_at: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "source": self.source,
            "kind": self.kind,
            "status": self.status,
            "title": self.title,
            "queued_at": self.queued_at,
            "priority": self.priority,
            "type": self.type,
            "tier": self.tier,
        }
        if self.goal:
            data["goal"] = self.goal
        if self.bead_id:
            data["bead_id"] = self.bead_id
        if self.lane:
            data["lane"] = self.lane
        if self.context:
            data["context"] = self.context
        if self.processed_at:
            data["processed_at"] = self.processed_at
        if self.error:
            data["error"] = self.error
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntakeEntry:
        return cls(
            id=data["id"],
            source=data["source"],
            kind=data["kind"],
            status=data["status"],
            title=data["title"],
            queued_at=data["queued_at"],
            goal=data.get("goal", ""),
            priority=data.get("priority", "P2"),
            type=data.get("type", "task"),
            tier=int(data.get("tier", 3)),
            bead_id=data.get("bead_id", ""),
            lane=data.get("lane", "") or str(data.get("context", {}).get("lane", "")),
            context=dict(data.get("context", {})),
            processed_at=data.get("processed_at", ""),
            error=data.get("error", ""),
        )


def default_queue_path(repo_root: Path | None = None) -> Path:
    return (repo_root or REPO_ROOT) / "07_LOGS_AND_AUDIT" / "intake_queue.jsonl"


def validate_entry(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("id", "source", "kind", "status", "title", "queued_at"):
        if key not in data or not str(data.get(key, "")).strip():
            errors.append(f"missing or empty: {key}")
    if data.get("source") not in VALID_SOURCES:
        errors.append(f"invalid source: {data.get('source')}")
    if data.get("kind") not in VALID_KINDS:
        errors.append(f"invalid kind: {data.get('kind')}")
    if data.get("status") not in VALID_STATUS:
        errors.append(f"invalid status: {data.get('status')}")
    if data.get("priority") and data.get("priority") not in VALID_PRIORITIES:
        errors.append(f"invalid priority: {data.get('priority')}")
    if data.get("type") and data.get("type") not in VALID_TYPES:
        errors.append(f"invalid type: {data.get('type')}")
    tier = data.get("tier")
    if tier is not None and (not isinstance(tier, int) or tier < 0 or tier > 4):
        errors.append("tier must be integer 0-4")
    kind = data.get("kind")
    if kind == "goal" and not str(data.get("goal", "")).strip():
        errors.append("kind=goal requires non-empty goal field")
    if kind == "bead_dispatch" and not str(data.get("bead_id", data.get("id", ""))).strip():
        errors.append("kind=bead_dispatch requires bead_id or id")
    lane = data.get("lane") or (data.get("context") or {}).get("lane")
    if lane and lane not in VALID_LANES:
        errors.append(f"invalid lane: {lane}")
    return errors


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_entry(data: dict[str, Any]) -> dict[str, Any]:
    """Fill defaults and coerce bead_dispatch id from bead_id."""
    out = dict(data)
    out.setdefault("status", "queued")
    out.setdefault("priority", "P2")
    out.setdefault("type", "task")
    out.setdefault("tier", 3)
    out.setdefault("queued_at", _utc_now())
    if not out.get("id"):
        out["id"] = f"intake-{uuid.uuid4().hex[:12]}"
    if out.get("kind") == "bead_dispatch":
        out.setdefault("bead_id", out["id"])
    if out.get("kind") == "goal" and not out.get("title") and out.get("goal"):
        out["title"] = str(out["goal"])[:120]
    return out


def append_entry(
    data: dict[str, Any],
    *,
    path: Path | None = None,
    repo_root: Path | None = None,
) -> IntakeEntry:
    """Append one validated entry to the intake queue."""
    path = path or default_queue_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_entry(data)
    errors = validate_entry(normalized)
    if errors:
        raise ValueError("; ".join(errors))

    entry = IntakeEntry.from_dict(normalized)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    return entry


def list_entries(
    *,
    path: Path | None = None,
    repo_root: Path | None = None,
) -> list[IntakeEntry]:
    path = path or default_queue_path(repo_root)
    if not path.is_file():
        return []
    entries: list[IntakeEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        entries.append(IntakeEntry.from_dict(json.loads(line)))
    return entries


def list_queued(
    *,
    path: Path | None = None,
    repo_root: Path | None = None,
) -> list[IntakeEntry]:
    """Return latest queued entry per id (dedupe by last write)."""
    by_id: dict[str, IntakeEntry] = {}
    for entry in list_entries(path=path, repo_root=repo_root):
        by_id[entry.id] = entry
    return [e for e in by_id.values() if e.status == "queued"]


def iter_queued(
    *,
    path: Path | None = None,
    repo_root: Path | None = None,
) -> Iterator[IntakeEntry]:
    yield from list_queued(path=path, repo_root=repo_root)


def record_status(
    entry: IntakeEntry,
    status: str,
    *,
    path: Path | None = None,
    repo_root: Path | None = None,
    error: str = "",
    bead_id: str = "",
) -> IntakeEntry:
    """Append status transition for an entry (append-only log)."""
    data = entry.to_dict()
    data["status"] = status
    data["processed_at"] = _utc_now()
    if error:
        data["error"] = error
    if bead_id:
        data["bead_id"] = bead_id
    return append_entry(data, path=path, repo_root=repo_root)
