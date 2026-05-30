#!/usr/bin/env python3
"""Audit whether Cursor, Claude, VS Code, and CLI wrappers point to repo-owned Harness scripts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_COMMANDS = [
    "scripts/new_session_bootstrap.py",
    "scripts/context_trim_audit.py",
    "scripts/context_rebuild.py",
    "scripts/daily_harness_audit.py",
    "scripts/validate_governance_stack.py",
    "scripts/workflow_git.py",
    "scripts/session_closeout.py",
]

CHECK_FILES = {
    "cursor_rule": ".cursor/rules/harness-audit.mdc",
    "cursor_hooks": ".cursor/hooks.json",
    "vscode_tasks": ".vscode/tasks.json",
    "claude_md": "CLAUDE.md",
    "agents_md": "AGENTS.md",
    "agent_operations": "AGENT_OPERATIONS.md",
}

CLOSEOUT_MARKERS = [
    "session_closeout",
    "sessionEnd",
    "Session Closeout",
]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def audit(root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    files: dict[str, Any] = {}

    for name, rel in CHECK_FILES.items():
        path = root / rel
        exists = path.exists()
        text = read_text(path) if exists else ""
        files[name] = {"path": rel, "exists": exists, "size": len(text)}
        if not exists and name in {"cursor_rule", "vscode_tasks", "agent_operations"}:
            findings.append({
                "severity": "P2",
                "code": "missing_wrapper_or_policy",
                "file": rel,
                "message": f"Expected IDE/policy file is missing: {rel}",
            })

    for command in REQUIRED_COMMANDS:
        script_exists = (root / command).exists()
        if not script_exists:
            findings.append({
                "severity": "P1",
                "code": "missing_repo_script",
                "file": command,
                "message": f"Required shared Harness script is missing: {command}",
            })

    wrapper_text = "\n".join(read_text(root / rel) for rel in CHECK_FILES.values())
    hooks_path = root / ".cursor" / "hooks" / "session_closeout.py"
    if not hooks_path.is_file():
        findings.append({
            "severity": "P2",
            "code": "missing_session_closeout_hook",
            "file": str(hooks_path.relative_to(root)),
            "message": "Cursor session closeout hook script missing",
        })
    elif not any(m in wrapper_text for m in CLOSEOUT_MARKERS):
        findings.append({
            "severity": "P2",
            "code": "closeout_not_wired",
            "file": ".cursor/hooks.json",
            "message": "Session closeout not referenced in IDE wrappers (sessionEnd / session_closeout)",
        })
    claude_hook = root / ".claude" / "hooks" / "session_closeout.sh"
    if not claude_hook.is_file():
        findings.append({
            "severity": "P2",
            "code": "missing_claude_closeout_hook",
            "file": str(claude_hook.relative_to(root)),
            "message": "Claude session closeout shell hook template missing",
        })

    for command in REQUIRED_COMMANDS:
        if command not in wrapper_text:
            findings.append({
                "severity": "P2",
                "code": "command_not_referenced",
                "file": command,
                "message": f"Shared command is not referenced by IDE/agent wrappers: {command}",
            })

    return {
        "audit": "ide_parity",
        "files": files,
        "required_commands": REQUIRED_COMMANDS,
        "findings": findings,
        "status": "fail" if any(f["severity"] in {"P0", "P1"} for f in findings) else "warn" if findings else "pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit(Path(args.root).resolve())
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
