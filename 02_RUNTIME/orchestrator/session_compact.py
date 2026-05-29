"""Persist session handoffs for harness agent continuity."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
_HANDOFFS = _REPO / "12_HANDOFFS" / "sessions"
_LATEST = _REPO / ".agents" / "handoffs" / "latest.json"
_TEMPLATE = _REPO / "12_HANDOFFS" / "AGENT_HANDOFF_TEMPLATE.md"


def _git(*args: str) -> str:
    try:
        return (
            subprocess.check_output(["git", *args], cwd=_REPO, text=True, stderr=subprocess.DEVNULL)
            .strip()
        )
    except Exception:
        return ""


def write_handoff(
    handoff_prep: dict[str, Any],
    *,
    mission: dict[str, Any] | None = None,
    agent: str = "harness",
    beads_ready: list[str] | None = None,
    next_command: str = "bd ready",
    test_status: str = "not_run",
    lint_status: str = "not_run",
    push_status: str = "unknown",
) -> Path:
    """Write handoff markdown + latest.json pointer."""
    mission = mission or {}
    mission_id = mission.get("mission_id") or handoff_prep.get("audit_log_ref") or "SESSION"
    _HANDOFFS.mkdir(parents=True, exist_ok=True)
    _LATEST.parent.mkdir(parents=True, exist_ok=True)

    branch = _git("branch", "--show-current") or "unknown"
    last_commit = _git("log", "-1", "--oneline") or "unknown"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot = handoff_prep.get("context_snapshot", {})
    goals = handoff_prep.get("next_session_goals", [])
    decision = handoff_prep.get("decision", "review")

    body = _TEMPLATE.read_text(encoding="utf-8") if _TEMPLATE.exists() else ""
    replacements = {
        "{{MISSION_ID}}": mission_id,
        "{{DATE}}": now[:10],
        "{{AGENT}}": agent,
        "{{BRANCH}}": branch,
        "{{LAST_COMMIT}}": last_commit,
        "{{DIRECTIVE_SUMMARY}}": handoff_prep.get("directive_summary", ""),
        "{{OBJECTIVE}}": snapshot.get("objective", mission.get("objective", "")),
        "{{AUTONOMY_LEVEL}}": str(snapshot.get("autonomy_level", mission.get("autonomy_level", "L1"))),
        "{{COMPOSITE_SCORE}}": str(snapshot.get("composite_score", "")),
        "{{DECISION}}": decision,
        "{{DONE_1}}": goals[0] if goals else "(see git log)",
        "{{DONE_2}}": goals[1] if len(goals) > 1 else "—",
        "{{DONE_3}}": goals[2] if len(goals) > 2 else "—",
        "{{TEST_STATUS}}": test_status,
        "{{LINT_STATUS}}": lint_status,
        "{{BEADS_STATUS}}": "see bd ready",
        "{{PUSH_STATUS}}": push_status,
        "{{BEAD_ID_1}}": (beads_ready or ["—"])[0],
        "{{BEAD_TITLE_1}}": "(run bd show)",
        "{{PRIORITY_1}}": "—",
        "{{NEXT_GOAL_1}}": goals[0] if goals else "Run bd ready and pick next issue",
        "{{NEXT_GOAL_2}}": goals[1] if len(goals) > 1 else "—",
        "{{NEXT_GOAL_3}}": goals[2] if len(goals) > 2 else "—",
        "{{NEXT_COMMAND}}": next_command,
        "{{RISK_1}}": f"Decision was '{decision}' — verify before auto-proceed",
        "{{RISK_2}}": "Read SESSION_COMPACT.md before starting new RPI epics",
    }
    for key, val in replacements.items():
        body = body.replace(key, val)

    out_path = _HANDOFFS / f"{mission_id}.md"
    out_path.write_text(body, encoding="utf-8")

    rel_handoff = out_path.relative_to(_REPO).as_posix()
    latest = {
        "updated_at": now,
        "agent": agent,
        "branch": branch,
        "last_commit": last_commit,
        "mission_id": mission_id,
        "handoff_path": rel_handoff,
        "beads_ready": beads_ready or [],
        "next_command": next_command,
        "decision": decision,
    }
    _LATEST.write_text(json.dumps(latest, indent=2) + "\n", encoding="utf-8")

    try:
        from intake.closure_feedback import enqueue_session_follow_ups

        enqueue_session_follow_ups(goals, mission_id=str(mission_id))
    except Exception:
        pass  # intake queue optional during bootstrap

    try:
        import sys

        runtime = _REPO / "02_RUNTIME"
        if str(runtime) not in sys.path:
            sys.path.insert(0, str(runtime))
        from knowledge.harvest_rigs import run_session_harvest

        run_session_harvest(_REPO, dry_run=False, min_confidence=0.6)
    except OSError:
        pass  # harvest optional when .agents trees missing

    return out_path
