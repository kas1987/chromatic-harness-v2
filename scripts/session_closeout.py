#!/usr/bin/env python3
"""Budget-aware session closeout: handoff, transfer packet, optional successor spawn.

Usage:
  python scripts/session_closeout.py --invoked-by cursor
  python scripts/session_closeout.py --invoked-by claude --harvest --spawn-successor
  python scripts/session_closeout.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from budget.ledger import BudgetLedger  # noqa: E402
from budget.transfer_packet import (  # noqa: E402
    build_transfer_packet,
    write_transfer_artifacts,
)
from orchestrator.session_compact import write_handoff  # noqa: E402


def _run(cmd: list[str], *, timeout: int = 120, cwd: Path | None = None) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd or _REPO,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 1, str(exc)


def git_snapshot() -> dict[str, Any]:
    snap: dict[str, Any] = {}
    for key, args in [
        ("branch", ["git", "branch", "--show-current"]),
        ("last_commit", ["git", "log", "-1", "--oneline"]),
        ("status_short", ["git", "status", "--short"]),
    ]:
        code, out = _run(args, timeout=30)
        if key == "status_short":
            snap[key] = out.splitlines() if out else []
        else:
            snap[key] = out if code == 0 else "unknown"
    return snap


def beads_ready_ids() -> list[str]:
    code, out = _run(["bd", "ready"], timeout=30)
    if code != 0 or not out:
        return []
    ids: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # bd ready often prints "id: title" or just id
        token = line.split()[0] if line else ""
        if token and not token.startswith("#"):
            ids.append(token.rstrip(":"))
    return ids[:10]


def log_activity(summary: str, *, bead_id: str = "", decision: str = "ok") -> None:
    _run(
        [
            sys.executable,
            str(_REPO / "scripts" / "log_agent_activity.py"),
            "log",
            "--event",
            "phase.complete",
            "--lane",
            "agent",
            "--summary",
            summary[:500],
            "--decision",
            decision,
        ],
        timeout=60,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Harness session closeout")
    parser.add_argument(
        "--invoked-by",
        choices=["cursor", "claude", "claude_code", "vscode", "cli", "codex", "scheduler"],
        default="cli",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--harvest", action="store_true", help="Run harvest_rigs --execute")
    parser.add_argument("--wiki-dry-run", action="store_true")
    parser.add_argument("--git-triage", action="store_true")
    parser.add_argument("--with-api", action="store_true", help="Phase C: optional API budget ingest")
    parser.add_argument(
        "--spawn-successor",
        action="store_true",
        help="Spawn when budget allows (also needs CHROMATIC_AUTO_SPAWN=1)",
    )
    parser.add_argument("--no-spawn", action="store_true", help="Never spawn successor")
    parser.add_argument("--summary", default="", help="Override closeout summary")
    parser.add_argument("--pytest", action="store_true", help="Run pytest tests/ -q")
    args = parser.parse_args()

    source = args.invoked_by
    if source == "claude":
        source = "claude_code"

    git = git_snapshot()
    beads = beads_ready_ids()
    ledger = BudgetLedger(_REPO)
    snapshot = ledger.snapshot()

    handoff_prep: dict[str, Any] = {
        "directive_summary": args.summary
        or f"Session closeout ({source}). Budget decision: {snapshot.decision}.",
        "decision": "review" if snapshot.decision != "halt_human" else "halt",
        "next_session_goals": [
            beads[0] if beads else "bd ready",
            "Read .agents/handoffs/transfer_packet.json",
            "Run new_session_bootstrap.py",
        ],
        "context_snapshot": {"objective": "Continue harness mission from handoff"},
        "risks": list(snapshot.reasons),
    }

    result: dict[str, Any] = {
        "invoked_by": source,
        "dry_run": args.dry_run,
        "git": git,
        "beads_ready": beads,
        "budget": snapshot.to_budget_dict(),
    }

    if args.dry_run:
        packet = build_transfer_packet(
            _REPO,
            source_runtime=source,
            snapshot=snapshot,
            handoff_prep=handoff_prep,
            handoff_path="12_HANDOFFS/sessions/DRY_RUN.md",
            beads_ready=beads,
            git_snapshot=git,
        )
        result["transfer_packet"] = packet
        print(json.dumps(result, indent=2))
        return 0

    handoff_path = write_handoff(
        handoff_prep,
        agent=source,
        beads_ready=beads,
        next_command="bd ready",
    )
    rel_handoff = handoff_path.relative_to(_REPO).as_posix()

    packet = build_transfer_packet(
        _REPO,
        source_runtime=source,
        snapshot=snapshot,
        handoff_prep=handoff_prep,
        handoff_path=rel_handoff,
        beads_ready=beads,
        git_snapshot=git,
    )
    write_transfer_artifacts(_REPO, packet)
    result["handoff_path"] = rel_handoff
    result["transfer_packet_path"] = ".agents/handoffs/transfer_packet.json"

    if args.harvest:
        _run([sys.executable, str(_REPO / "scripts" / "harvest_rigs.py"), "--execute"], timeout=180)

    if args.wiki_dry_run:
        _run(
            [sys.executable, str(_REPO / "scripts" / "promote_to_wiki.py"), "--dry-run"],
            timeout=120,
        )

    if args.git_triage:
        _run(
            [sys.executable, str(_REPO / "scripts" / "git_triage.py"), "--from-log"],
            timeout=90,
        )

    if args.pytest:
        code, out = _run([sys.executable, "-m", "pytest", "tests/", "-q"], timeout=600)
        result["pytest_exit"] = code
        if code != 0:
            handoff_prep["risks"].append(f"pytest failed (exit {code})")

    log_activity(
        args.summary or f"session closeout ({source}); budget={snapshot.decision}",
        decision="ok" if snapshot.decision != "halt_human" else "halt",
    )

    spawn = False
    if not args.no_spawn and snapshot.decision == "spawn":
        if args.spawn_successor or os.environ.get("CHROMATIC_AUTO_SPAWN", "").strip() in (
            "1",
            "true",
            "yes",
        ):
            spawn = True

    if spawn:
        code, out = _run(
            [
                sys.executable,
                str(_REPO / "scripts" / "spawn_successor_agent.py"),
                "--packet",
                str(_REPO / ".agents" / "handoffs" / "transfer_packet.json"),
            ],
            timeout=120,
        )
        result["spawn_exit"] = code
        result["spawn_output"] = out[:2000]
    else:
        result["spawn"] = "skipped"
        result["spawn_reason"] = (
            "budget or CHROMATIC_AUTO_SPAWN"
            if snapshot.decision != "spawn"
            else "not requested"
        )

    if args.with_api:
        result["with_api"] = "not_implemented_phase_c"

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
