"""Build Agent Transfer Packet and successor prompt."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ledger import BudgetLedger, BudgetSnapshot, load_agent_budget_config


def write_successor_prompt(
    repo_root: Path,
    *,
    packet: dict[str, Any],
    handoff_path: str,
) -> Path:
    out = repo_root / ".agents" / "handoffs" / "successor_prompt.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    budget = packet.get("budget") or {}
    lines = [
        "# Successor Agent Prompt",
        "",
        f"**Transfer ID:** {packet.get('transfer_id', '')}",
        f"**Budget decision:** {budget.get('decision', 'handoff_only')}",
        "",
        "## Objective",
        "",
        packet.get("objective") or "(see handoff)",
        "",
        "## Summary",
        "",
        (packet.get("summary") or "")[:3000],
        "",
        "## Next action",
        "",
        packet.get("next_action") or "bd ready",
        "",
        "## Risks",
        "",
    ]
    for r in packet.get("risks") or []:
        lines.append(f"- {r}")
    if packet.get("blockers"):
        lines.append("")
        lines.append("## Blockers")
        lines.append("")
        for b in packet["blockers"]:
            lines.append(f"- {b}")
    lines.extend(
        [
            "",
            "## Handoff",
            "",
            f"- Markdown: `{handoff_path}`",
            "- Packet: `.agents/handoffs/transfer_packet.json`",
            "",
            "## Boot (run first)",
            "",
        ]
    )
    for cmd in packet.get("boot_commands") or []:
        lines.append(f"- `{cmd}`")
    lines.append("")
    lines.append("Do not load full transcripts or bulk JSONL logs.")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def build_transfer_packet(
    repo_root: Path,
    *,
    source_runtime: str,
    snapshot: BudgetSnapshot,
    handoff_prep: dict[str, Any] | None = None,
    handoff_path: str = "",
    beads_ready: list[str] | None = None,
    git_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = load_agent_budget_config(repo_root)
    handoff_prep = handoff_prep or {}
    goals = handoff_prep.get("next_session_goals") or []
    spawn_mode = "auto" if snapshot.decision == "spawn" else "manual"
    successor_runtime = os.environ.get("CHROMATIC_SUCCESSOR_RUNTIME") or cfg.get(
        "default_successor_runtime", "cursor"
    )

    packet: dict[str, Any] = {
        "transfer_id": str(uuid.uuid4()),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_runtime": source_runtime,
        "objective": handoff_prep.get("context_snapshot", {}).get("objective", "")
        or (git_snapshot or {}).get("objective", "")
        or "Resume harness work from handoff",
        "decision": handoff_prep.get("decision", "review"),
        "summary": handoff_prep.get("directive_summary", "")[:2000]
        or f"Closeout from {source_runtime}. Budget: {snapshot.decision}.",
        "evidence_refs": handoff_prep.get("evidence_refs", []),
        "files_touched": handoff_prep.get("files_touched", []),
        "risks": handoff_prep.get("risks", [])
        or [f"Budget decision: {snapshot.decision}"],
        "blockers": handoff_prep.get("blockers", []),
        "next_action": goals[0] if goals else "bd ready",
        "confidence": handoff_prep.get("confidence", 70),
        "budget_used": handoff_prep.get("budget_used")
        or {"tool_calls": 0, "files_read": 0, "approx_tokens": snapshot.session_est_tokens},
        "successor": {
            "runtime": successor_runtime,
            "model_hint": "",
            "spawn_mode": spawn_mode,
            "prompt_path": ".agents/handoffs/successor_prompt.md",
        },
        "budget": snapshot.to_budget_dict(),
        "beads_ready": beads_ready or [],
        "boot_commands": cfg.get("boot_commands")
        or [
            "python scripts/new_session_bootstrap.py --root .",
            "bd ready",
        ],
        "forbidden": ["full_transcript", "bulk_jsonl_scan"],
        "handoff_path": handoff_path,
        "latest_pointer": ".agents/handoffs/latest.json",
    }
    if git_snapshot:
        packet["git"] = git_snapshot
    return packet


def write_transfer_artifacts(
    repo_root: Path,
    packet: dict[str, Any],
) -> tuple[Path, Path]:
    handoffs = repo_root / ".agents" / "handoffs"
    handoffs.mkdir(parents=True, exist_ok=True)
    packet_path = handoffs / "transfer_packet.json"
    packet_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    prompt_path = write_successor_prompt(
        repo_root,
        packet=packet,
        handoff_path=packet.get("handoff_path", ""),
    )
    latest_path = handoffs / "latest.json"
    if latest_path.is_file():
        try:
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            latest = {}
        latest["transfer_packet_path"] = ".agents/handoffs/transfer_packet.json"
        latest["budget_decision"] = (packet.get("budget") or {}).get("decision", "")
        latest["updated_at"] = packet.get("updated_at", latest.get("updated_at", ""))
        latest_path.write_text(json.dumps(latest, indent=2) + "\n", encoding="utf-8")
    return packet_path, prompt_path
