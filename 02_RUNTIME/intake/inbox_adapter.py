"""Poll Chromatic Inbox Harness SQLite queue into repo intake_queue.jsonl."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from intake.queue import append_entry, default_queue_path, list_entries

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_STATE = REPO_ROOT / ".agents" / "intake" / "inbox_sync.state.json"

PENDING_STATUSES = ("pending", "new", "retry")
INBOX_ROOT_CANDIDATES = (
    os.environ.get("CHROMATIC_INBOX_ROOT", ""),
    "C:/chromatic-inbox-harness-data",
    "C:/Repos/Poly-Chromatic/chromatic-inbox-harness-data",
)


@dataclass
class InboxPollReport:
    inbox_root: str = ""
    db_path: str = ""
    fetched: int = 0
    appended: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inbox_root": self.inbox_root,
            "db_path": self.db_path,
            "fetched": self.fetched,
            "appended": self.appended,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def resolve_inbox_root() -> Path | None:
    for raw in INBOX_ROOT_CANDIDATES:
        if not raw:
            continue
        root = Path(raw)
        db = root / "db" / "chromatic_inbox.sqlite"
        if db.is_file():
            return root
    return None


def resolve_inbox_db(explicit: Path | None = None) -> Path | None:
    if explicit and explicit.is_file():
        return explicit
    root = resolve_inbox_root()
    if root:
        db = root / "db" / "chromatic_inbox.sqlite"
        return db if db.is_file() else None
    return None


def _load_sync_state() -> set[str]:
    if not SYNC_STATE.is_file():
        return set()
    try:
        data = json.loads(SYNC_STATE.read_text(encoding="utf-8"))
        return set(data.get("synced_ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_sync_state(synced: set[str]) -> None:
    SYNC_STATE.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATE.write_text(
        json.dumps({"synced_ids": sorted(synced)[-5000:]}, indent=2) + "\n",
        encoding="utf-8",
    )


def _normalize_priority(raw: Any) -> str:
    text = str(raw or "P2").upper().strip()
    if text in ("P0", "P1", "P2", "P3"):
        return text
    if text.isdigit():
        n = int(text)
        return {0: "P0", 1: "P1", 2: "P2", 3: "P3"}.get(n, "P2")
    return "P2"


def _map_row_to_intake(row: sqlite3.Row) -> dict[str, Any]:
    item_id = str(row["id"])
    subject = str(row["subject"] or "Inbox item")[:200]
    source = str(row["source"] or "inbox")
    body = ""
    if "body" in row.keys():
        body = str(row["body"] or "")
    elif "summary" in row.keys():
        body = str(row["summary"] or "")

    goal = subject
    if body:
        goal = f"{subject}\n\n{body[:2000]}"

    return {
        "id": f"inbox-{item_id}",
        "source": "inbox",
        "kind": "goal",
        "status": "queued",
        "title": subject,
        "goal": goal,
        "priority": _normalize_priority(row["priority"] if "priority" in row.keys() else "P2"),
        "type": "task",
        "tier": 2,
        "context": {
            "inbox_id": item_id,
            "inbox_source": source,
            "inbox_status": str(row["status"] if "status" in row.keys() else ""),
        },
    }


def fetch_pending_items(db_path: Path, *, limit: int | None = 50) -> list[dict[str, Any]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in PENDING_STATUSES)
        sql = f"""
            SELECT * FROM queue_items
            WHERE status IN ({placeholders})
            ORDER BY priority DESC, created_at DESC
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = conn.execute(sql, PENDING_STATUSES).fetchall()
        return [_map_row_to_intake(r) for r in rows]
    finally:
        conn.close()


def _already_queued(inbox_entry_id: str, queue_path: Path) -> bool:
    for entry in list_entries(path=queue_path):
        if entry.id == inbox_entry_id:
            return entry.status in ("queued", "processing")
    return False


def poll_inbox_to_intake(
    *,
    db_path: Path | None = None,
    repo_root: Path | None = None,
    limit: int | None = 50,
    dry_run: bool = False,
) -> InboxPollReport:
    """Fetch pending inbox items and append to harness intake queue."""
    report = InboxPollReport()
    resolved = resolve_inbox_db(db_path)
    if not resolved:
        report.errors.append("chromatic_inbox.sqlite not found (set CHROMATIC_INBOX_ROOT)")
        return report

    report.db_path = str(resolved)
    root = resolved.parent.parent
    report.inbox_root = str(root)

    queue_path = default_queue_path(repo_root)
    synced = _load_sync_state()
    items = fetch_pending_items(resolved, limit=limit)
    report.fetched = len(items)

    for item in items:
        entry_id = item["id"]
        inbox_id = item["context"]["inbox_id"]
        if inbox_id in synced or _already_queued(entry_id, queue_path):
            report.skipped += 1
            continue
        if dry_run:
            report.appended += 1
            synced.add(inbox_id)
            continue
        try:
            append_entry(item, path=queue_path, repo_root=repo_root)
            report.appended += 1
            synced.add(inbox_id)
        except ValueError as exc:
            report.errors.append(f"{entry_id}: {exc}")

    if not dry_run:
        _save_sync_state(synced)
    return report
