#!/usr/bin/env python3
"""Queue dispatcher for Chromatic review intake (PDR S5 Phase 3).

Selects ready ``next_work_item`` records, enforces one-mutating-agent-per-PR via
branch locks, renders an agent mission packet from the template, and writes a
schema-valid ``agent_dispatch`` record. Agents consume governed queue items only;
they never wander GitHub looking for work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import lock_pr_branch

DEFAULT_BASE = "07_LOGS_AND_AUDIT/review_intake"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = REPO_ROOT / "templates" / "AGENT_MISSION_PACKET_REVIEW_INTAKE.md"

GATED_STATUSES = {"needs-human-decision", "blocked", "review-required", "in-progress", "done"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return f"{prefix}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12].upper()}"


def load_queue(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.read_text().strip():
        return {"items": []}
    data = json.loads(path.read_text())
    if isinstance(data, list):
        data = {"items": data}
    data.setdefault("items", [])
    return data


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def render_mission_packet(template: str, item: Dict[str, Any]) -> str:
    allowed = item.get("allowed_files") or []
    forbidden = ["Any file outside the Allowed Files list", "CI/secret/security config unless explicitly scoped"]
    acceptance = item.get("acceptance_checks") or ["Review manually"]
    stop = [
        "Stop if the change would touch a file not in Allowed Files.",
        "Stop and escalate if the finding is security/architecture and not explicitly approved.",
        "Stop if validation evidence cannot be produced.",
    ]
    mapping = {
        "task_id": item.get("id", "unknown"),
        "objective": item.get("title", ""),
        "source_links": "\n".join(f"- {link}" for link in (item.get("links") or [])) or "- (none)",
        "allowed_files": "\n".join(f"- `{f}`" for f in allowed) or "- (PR-level: no single file scoped)",
        "forbidden_files": "\n".join(f"- {f}" for f in forbidden),
        "risk_level": item.get("risk_level", "unknown"),
        "confidence_score": str(item.get("confidence_score", 0)),
        "acceptance_checks": "\n".join(f"- {c}" for c in acceptance),
        "stop_conditions": "\n".join(f"- {c}" for c in stop),
    }
    out = template
    for key, value in mapping.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def _bd_priority(item: Dict[str, Any]) -> str:
    """Map review risk/confidence onto a bd priority (P0 highest .. P4 lowest)."""
    if item.get("risk_level") == "high":
        return "1"
    score = int(item.get("confidence_score", 0))
    if score >= 75:
        return "2"
    if score >= 40:
        return "3"
    return "4"


def create_bead(item: Dict[str, Any], bd_bin: str = "bd") -> str | None:
    """Create a bead for a dispatched review finding so it enters the live `bd ready` loop.

    Returns the new bead id, or None if bd is unavailable or the call fails. The dispatcher
    never blocks on bd: a missing tracker degrades to mission-packet-only dispatch.
    """
    if not shutil.which(bd_bin):
        return None
    title = item.get("title") or f"Review finding {item.get('source_finding_id')}"
    acceptance = "\n".join(f"- {c}" for c in (item.get("acceptance_checks") or []))
    links = "\n".join(item.get("links") or [])
    description = (
        f"{item.get('notes', '')}\n\n"
        f"Source finding: {item.get('source_finding_id')}\n"
        f"Allowed files: {', '.join(item.get('allowed_files') or []) or '(PR-level)'}\n"
        f"Links:\n{links}".strip()
    )
    cmd = [
        bd_bin,
        "create",
        title,
        "--priority",
        _bd_priority(item),
        "--description",
        description,
        "--acceptance",
        acceptance or "Address the review finding and provide validation evidence.",
        "--labels",
        "review-intake",
        "--external-ref",
        str(item.get("source_finding_id") or item.get("id")),
    ]
    assignee = item.get("owner_agent")
    if assignee:
        cmd += ["--assignee", assignee]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"Created issue:\s*(\S+)", result.stdout)
    return match.group(1) if match else None


def dispatch_item(
    item: Dict[str, Any],
    lock_dir: Path,
    packet_dir: Path,
    dispatch_log: Path,
    template: str,
    ttl_minutes: int,
    emit_beads: bool = False,
    bd_bin: str = "bd",
) -> Dict[str, Any]:
    repo = item.get("repo") or "unknown/repo"
    pr_number = item.get("pr_number")
    agent = item.get("owner_agent", "Auditor")
    task_id = item.get("id", "unknown")

    # Collision control: one mutating agent per PR branch.
    lock_acquired = True
    lock_record = None
    if pr_number is not None:
        lock_acquired, payload = lock_pr_branch.acquire(
            lock_dir,
            repo,
            int(pr_number),
            holder=agent,
            queue_item_id=task_id,
            ttl_minutes=ttl_minutes,
        )
        if not lock_acquired:
            return {"task_id": task_id, "dispatched": False, "reason": "pr_branch_locked", "lock": payload.get("lock")}
        lock_record = payload

    packet = render_mission_packet(template, item)
    packet_dir.mkdir(parents=True, exist_ok=True)
    packet_path = packet_dir / f"{task_id}.md"
    packet_path.write_text(packet, encoding="utf-8")

    # Live-loop bridge: register the finding as a bead so it enters `bd ready`.
    # Idempotent — an item already carrying a bead_id is not re-created.
    bead_id = item.get("bead_id")
    if emit_beads and not bead_id:
        bead_id = create_bead(item, bd_bin=bd_bin)
        if bead_id:
            item["bead_id"] = bead_id

    dispatch = {
        "dispatch_id": stable_id("AD", repo, pr_number, task_id, utc_now()),
        "task_id": task_id,
        "agent": agent,
        "status": "dispatched",
        "repo": repo,
        "pr_number": pr_number if pr_number is None else int(pr_number),
        "started_at": utc_now(),
        "completed_at": None,
        "validation_summary": None,
        "links": item.get("links") or [],
        "mission_packet": str(packet_path.relative_to(REPO_ROOT))
        if packet_path.is_relative_to(REPO_ROOT)
        else str(packet_path),
        "lock_id": (lock_record or {}).get("lock_id"),
        "bead_id": bead_id,
    }
    append_jsonl(dispatch_log, dispatch)
    return {
        "task_id": task_id,
        "dispatched": True,
        "dispatch_id": dispatch["dispatch_id"],
        "agent": agent,
        "mission_packet": dispatch["mission_packet"],
        "bead_id": bead_id,
    }


def select_ready(queue: Dict[str, Any]) -> List[Dict[str, Any]]:
    ready = [i for i in queue.get("items", []) if i.get("status") == "ready"]
    return sorted(ready, key=lambda i: i.get("priority", 0), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default=f"{DEFAULT_BASE}/queue.json")
    parser.add_argument("--lock-dir", default=f"{DEFAULT_BASE}/locks")
    parser.add_argument("--packet-dir", default=f"{DEFAULT_BASE}/mission_packets")
    parser.add_argument("--dispatch-log", default=f"{DEFAULT_BASE}/dispatch_log.jsonl")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--limit", type=int, default=1, help="Max items to dispatch this run")
    parser.add_argument("--ttl-minutes", type=int, default=30)
    parser.add_argument(
        "--emit-beads", action="store_true", help="Register each dispatched item as a bead (enters `bd ready`)"
    )
    parser.add_argument("--bd-bin", default="bd", help="bd executable (override for testing)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    queue_path = Path(args.queue)
    queue = load_queue(queue_path)
    template = Path(args.template).read_text(encoding="utf-8")
    ready = select_ready(queue)

    results: List[Dict[str, Any]] = []
    dispatched = 0
    for item in ready:
        if dispatched >= args.limit:
            break
        if args.dry_run:
            results.append({"task_id": item.get("id"), "would_dispatch": True, "agent": item.get("owner_agent")})
            dispatched += 1
            continue
        result = dispatch_item(
            item,
            Path(args.lock_dir),
            Path(args.packet_dir),
            Path(args.dispatch_log),
            template,
            args.ttl_minutes,
            emit_beads=args.emit_beads,
            bd_bin=args.bd_bin,
        )
        results.append(result)
        if result.get("dispatched"):
            item["status"] = "in-progress"
            item["updated_at"] = utc_now()
            dispatched += 1

    if not args.dry_run and dispatched:
        queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"ready_count": len(ready), "dispatched": dispatched, "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
