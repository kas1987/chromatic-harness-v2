#!/usr/bin/env python3
"""
Chromatic Harness v2: Context Rebuild

Builds a minimal context manifest from durable project state.
Does not delete files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALWAYS_LOAD = [
    ".agents/context/BOOT_CONTEXT.md",
    ".agents/handoffs/latest.json",
    "active handoff referenced by latest.json",
    "selected bd issue details",
    "git branch/status summary",
]

LOAD_IF_RELEVANT = [
    "AGENT_OPERATIONS.md",
    "docs/governance/PRE_SESSION_CONTEXT_POLICY.md",
    "docs/governance/CONTEXT_REBUILD_POLICY.md",
    "docs/governance/OPENROUTER_BROKER_POLICY.md",
    "docs/BEADS_OBJECT_MODEL.md",
    "04_PLAYBOOKS/*.md for selected mission only",
    "09_DEPLOYMENT/config/routing/*.yaml for routing work only",
]

NEVER_AUTO_LOAD = [
    "~/.claude/projects/**/*.jsonl",
    "07_LOGS_AND_AUDIT/**/*.jsonl",
    "traces/**/*.jsonl",
    "old handoff chains",
    "archive folders",
    "entire docs folder",
    "entire repository tree",
    "full deployment guide unless deployment is active mission",
]


@dataclass
class CommandResult:
    available: bool
    stdout: str
    stderr: str
    returncode: int | None


@dataclass
class ContextManifest:
    generated_at: str
    mode: str
    repo_root: str
    git: dict[str, Any]
    handoff: dict[str, Any]
    beads: dict[str, Any]
    context_policy: dict[str, list[str]]
    audit: dict[str, Any]
    next_action: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_command(args: list[str], cwd: Path, timeout: int = 10) -> CommandResult:
    try:
        proc = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)
        return CommandResult(True, proc.stdout.strip(), proc.stderr.strip(), proc.returncode)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return CommandResult(False, "", str(exc), None)


def git_state(root: Path) -> dict[str, Any]:
    branch = run_command(["git", "branch", "--show-current"], root)
    status = run_command(["git", "status", "--short"], root)
    log = run_command(["git", "log", "-1", "--oneline"], root)
    return {
        "available": branch.available and branch.returncode == 0,
        "branch": branch.stdout if branch.stdout else "unknown",
        "status_short": status.stdout.splitlines() if status.stdout else [],
        "last_commit": log.stdout if log.stdout else "unknown",
        "errors": [x.stderr for x in [branch, status, log] if x.stderr],
    }


def handoff_state(root: Path) -> dict[str, Any]:
    pointer = root / ".agents" / "handoffs" / "latest.json"
    transfer_path = root / ".agents" / "handoffs" / "transfer_packet.json"
    state: dict[str, Any] = {
        "latest_pointer_exists": pointer.exists(),
        "latest_pointer_path": str(pointer.relative_to(root)) if pointer.exists() else None,
        "handoff_path": None,
        "transfer_packet_exists": transfer_path.is_file(),
        "transfer_packet_path": (
            str(transfer_path.relative_to(root)) if transfer_path.is_file() else None
        ),
        "budget_decision": None,
        "boot_commands": [],
        "raw": None,
        "error": None,
    }
    if transfer_path.is_file():
        try:
            tp = json.loads(transfer_path.read_text(encoding="utf-8"))
            state["transfer_packet"] = {
                "updated_at": tp.get("updated_at"),
                "budget_decision": (tp.get("budget") or {}).get("decision"),
            }
            state["budget_decision"] = (tp.get("budget") or {}).get("decision")
            state["boot_commands"] = tp.get("boot_commands") or []
        except Exception as exc:  # noqa: BLE001
            state["transfer_packet_error"] = str(exc)
    if not pointer.exists():
        return state
    try:
        raw = json.loads(pointer.read_text(encoding="utf-8"))
        state["raw"] = raw
        for key in ["handoff_path", "path", "file", "latest_handoff"]:
            if isinstance(raw, dict) and raw.get(key):
                state["handoff_path"] = raw[key]
                break
        if raw.get("budget_decision"):
            state["budget_decision"] = raw["budget_decision"]
        if raw.get("transfer_packet_path"):
            state["transfer_packet_path"] = raw["transfer_packet_path"]
    except Exception as exc:  # noqa: BLE001 - robust audit script
        state["error"] = str(exc)
    return state


def beads_state(root: Path) -> dict[str, Any]:
    ready = run_command(["bd", "ready"], root, timeout=15)
    return {
        "available": ready.available and ready.returncode == 0,
        "ready_summary": ready.stdout if ready.stdout else "bd unavailable or no ready output",
        "error": ready.stderr if ready.stderr else None,
    }


def load_audit(root: Path) -> dict[str, Any]:
    audit_path = root / ".agents" / "context" / "context_trim_audit.json"
    if not audit_path.exists():
        return {"available": False, "risk_level": "unknown", "findings": []}
    try:
        data = json.loads(audit_path.read_text(encoding="utf-8"))
        return {"available": True, **data}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "risk_level": "unknown", "findings": [], "error": str(exc)}


def build_manifest(root: Path, mode: str) -> ContextManifest:
    audit = load_audit(root)
    next_action = "Select one active bead and load only task-relevant docs."
    if mode == "hard":
        next_action = "Restart from .agents/context/BOOT_CONTEXT.md and selected bead only."
    elif mode == "nuclear":
        next_action = "Treat old logs, old handoffs, and archives as quarantine-only until human review."

    return ContextManifest(
        generated_at=utc_now(),
        mode=mode,
        repo_root=str(root),
        git=git_state(root),
        handoff=handoff_state(root),
        beads=beads_state(root),
        context_policy={
            "always_load": ALWAYS_LOAD,
            "load_if_relevant": LOAD_IF_RELEVANT,
            "never_auto_load": NEVER_AUTO_LOAD,
        },
        audit={
            "risk_level": audit.get("risk_level", "unknown"),
            "summary": audit.get("summary", {}),
            "findings": audit.get("findings", []),
        },
        next_action=next_action,
    )


def write_summary(root: Path, manifest: ContextManifest) -> None:
    out = root / ".agents" / "context" / "context_rebuild_summary.md"
    lines = [
        "# Context Rebuild Summary",
        "",
        f"Generated: {manifest.generated_at}",
        f"Mode: {manifest.mode}",
        f"Risk Level: {manifest.audit.get('risk_level', 'unknown')}",
        "",
        "## Git",
        "",
        f"Branch: `{manifest.git.get('branch', 'unknown')}`",
        "",
        "```text",
        "\n".join(manifest.git.get("status_short", [])) or "clean or unavailable",
        "```",
        "",
        "## Handoff",
        "",
        f"Pointer exists: {manifest.handoff.get('latest_pointer_exists')}",
        f"Handoff path: {manifest.handoff.get('handoff_path')}",
        "",
        "## Beads",
        "",
        "```text",
        str(manifest.beads.get("ready_summary", "bd unavailable"))[:4000],
        "```",
        "",
        "## Next Action",
        "",
        manifest.next_action,
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild minimal context manifest for Chromatic Harness v2.")
    parser.add_argument("--root", default=".", help="Repository root. Default: current directory.")
    parser.add_argument("--mode", choices=["soft", "hard", "nuclear"], default="soft")
    parser.add_argument("--out", default=".agents/context/context_rebuild_manifest.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(root, args.mode)
    out_path.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    write_summary(root, manifest)

    print(f"Context manifest written: {out_path}")
    print(f"Mode: {args.mode}")
    print(f"Risk: {manifest.audit.get('risk_level', 'unknown')}")
    print(f"Next: {manifest.next_action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
