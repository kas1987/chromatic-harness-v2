#!/usr/bin/env python3
"""Verify Claude Code project settings meet Harness production requirements."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SETTINGS = REPO / ".claude" / "settings.json"
WORKFLOWS_SRC = REPO / ".claude" / "workflows"
HOME_WF = Path.home() / ".claude" / "workflows"


def _hook_commands(settings: dict, event: str) -> list[str]:
    cmds: list[str] = []
    for block in settings.get("hooks", {}).get(event, []) or []:
        if not isinstance(block, dict):
            continue
        for h in block.get("hooks", []):
            if isinstance(h, dict) and h.get("command"):
                cmds.append(str(h["command"]))
    return cmds


def _global_session_start_count() -> int | None:
    global_path = Path.home() / ".claude" / "settings.json"
    if not global_path.is_file():
        return 0
    try:
        doc = json.loads(global_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    blocks = doc.get("hooks", {}).get("SessionStart", []) or []
    return len(blocks) if isinstance(blocks, list) else None


def validate(root: Path | None = None, *, machine_checks: bool | None = None) -> list[str]:
    root = root or REPO
    if machine_checks is None:
        machine_checks = not (os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))
    errors: list[str] = []

    if not SETTINGS.is_file():
        errors.append("Missing .claude/settings.json")
        return errors

    try:
        doc = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f".claude/settings.json invalid JSON: {exc}")
        return errors

    start_cmds = _hook_commands(doc, "SessionStart")
    if not any("session_start.py" in c for c in start_cmds):
        errors.append("SessionStart must run python scripts/session_start.py")

    end_cmds = _hook_commands(doc, "SessionEnd")
    if not any("session_closeout.py" in c for c in end_cmds):
        errors.append("SessionEnd must run python scripts/session_closeout.py --invoked-by claude_code")

    agent_gates = [
        c
        for c in _hook_commands(doc, "PreToolUse")
        if "gate.py" in c
    ]
    if len(agent_gates) != 1:
        errors.append("PreToolUse Agent must have exactly one gate.py hook")

    for wf in ("ship.js", "close-issue.js", "qa.js", "go.js"):
        if not (WORKFLOWS_SRC / wf).is_file():
            errors.append(f"Missing lite workflow: .claude/workflows/{wf}")

    if machine_checks:
        installed = HOME_WF / "ship.js"
        if not installed.is_file():
            errors.append(
                "Lite workflows not installed in ~/.claude/workflows — run scripts/sync_claude_workflows.ps1"
            )
        else:
            text = installed.read_text(encoding="utf-8", errors="replace").lower()
            if "label:" in text and "/crank" in text and "do not run /crank" not in text:
                errors.append(
                    "~/.claude/workflows/ship.js still invokes /crank — re-run sync_claude_workflows.ps1"
                )

        gcount = _global_session_start_count()
        if gcount is None:
            errors.append("~/.claude/settings.json is invalid JSON")
        elif gcount > 0:
            errors.append(
                f"Global Claude has {gcount} SessionStart hook(s) — run "
                "python scripts/slim_claude_global_hooks.py --apply for harness-lean sessions"
            )

    return errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--repo-only",
        action="store_true",
        help="Only validate committed .claude/settings.json (for CI)",
    )
    parser.add_argument(
        "--machine",
        action="store_true",
        help="Also validate ~/.claude workflows and global hook slim state",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.repo_only:
        machine = False
    elif args.machine:
        machine = True
    else:
        machine = None

    errors = validate(root, machine_checks=machine)
    if errors:
        print("Claude harness validation FAILED", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("Claude harness validation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
