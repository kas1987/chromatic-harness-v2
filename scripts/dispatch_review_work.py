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


def dispatch_item(
    item: Dict[str, Any],
    lock_dir: Path,
    packet_dir: Path,
    dispatch_log: Path,
    template: str,
    ttl_minutes: int,
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
    }
    append_jsonl(dispatch_log, dispatch)
    return {
        "task_id": task_id,
        "dispatched": True,
        "dispatch_id": dispatch["dispatch_id"],
        "agent": agent,
        "mission_packet": dispatch["mission_packet"],
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
