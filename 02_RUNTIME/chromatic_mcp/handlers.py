"""MCP tool handlers — thin wrappers around harness scripts (testable without MCP runtime)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
_RUNTIME = REPO_ROOT / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

def _session_id(raw: str | None) -> str:
    sid = (raw or "").strip()
    if sid:
        return sid
    return "anonymous-session"


def _run_script(script: str, *args: str, timeout: int = 120) -> dict[str, Any]:
    proc = subprocess.run(
        [PYTHON, str(REPO_ROOT / "scripts" / script), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-8000:],
        "stderr": (proc.stderr or "")[-2000:],
    }


def workflow_go(mode: str = "GO") -> dict[str, Any]:
    return _run_script("workflow_go.py", mode)


def workflow_git_ship(*, dry_run: bool = True, session_id: str | None = None) -> dict[str, Any]:
    args = ["ship", "--from-log", "--verifier", "approve", "--run-tests"]
    if not dry_run:
        args.append("--execute")
    args.extend(["--session-id", _session_id(session_id), "--lock-timeout", "30"])
    return _run_script("workflow_git.py", *args, timeout=300)


def auto_intake(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    args: list[str] = []
    if dry_run:
        args.append("--dry-run")
    if limit is not None:
        args.extend(["--limit", str(limit)])
    args.extend(["--session-id", _session_id(session_id), "--lock-timeout", "30"])
    return _run_script("auto_intake.py", *args)


def poll_inbox(
    *,
    dry_run: bool = False,
    limit: int = 20,
    session_id: str | None = None,
) -> dict[str, Any]:
    args = ["--limit", str(limit)]
    if dry_run:
        args.append("--dry-run")
    args.extend(["--session-id", _session_id(session_id), "--lock-timeout", "30"])
    return _run_script("poll_inbox.py", *args)


def intake_queue_list() -> dict[str, Any]:
    from intake.queue import list_queued

    queued = list_queued(repo_root=REPO_ROOT)
    return {
        "ok": True,
        "count": len(queued),
        "items": [e.to_dict() for e in queued],
    }


def beads_ready() -> dict[str, Any]:
    bd_exec = shutil.which("bd")
    cmd = [bd_exec, "ready"] if bd_exec else [PYTHON, "-m", "beads", "ready"]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "command": " ".join(cmd),
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


def check_operations() -> dict[str, Any]:
    return _run_script("check_agent_operations.py")


def validate_intake_loop() -> dict[str, Any]:
    return _run_script("validate_intake_loop.py")


def parallel_health(*, prune: bool = False) -> dict[str, Any]:
    args: list[str] = []
    if prune:
        args.append("--prune")
    return _run_script("parallel_health.py", *args)


def session_guard(
    *,
    surface: str = "mcp",
    invoked_by: str = "automation",
    force: bool = False,
    full: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    args: list[str] = ["--surface", surface, "--invoked-by", invoked_by]
    if force:
        args.append("--force")
    if full:
        args.append("--full")
    if dry_run:
        args.append("--dry-run")
    return _run_script("session_unified_guard.py", *args, timeout=900)


HANDLERS: dict[str, Any] = {
    "workflow_go": lambda args: workflow_go(args.get("mode", "GO")),
    "workflow_git_ship": lambda args: workflow_git_ship(
        dry_run=args.get("dry_run", True),
        session_id=args.get("session_id"),
    ),
    "auto_intake": lambda args: auto_intake(
        dry_run=args.get("dry_run", False),
        limit=args.get("limit"),
        session_id=args.get("session_id"),
    ),
    "poll_inbox": lambda args: poll_inbox(
        dry_run=args.get("dry_run", False),
        limit=int(args.get("limit", 20)),
        session_id=args.get("session_id"),
    ),
    "intake_queue_list": lambda _args: intake_queue_list(),
    "beads_ready": lambda _args: beads_ready(),
    "check_agent_operations": lambda _args: check_operations(),
    "validate_intake_loop": lambda _args: validate_intake_loop(),
    "parallel_health": lambda args: parallel_health(prune=args.get("prune", False)),
    "session_guard": lambda args: session_guard(
        surface=str(args.get("surface", "mcp")),
        invoked_by=str(args.get("invoked_by", "automation")),
        force=bool(args.get("force", False)),
        full=bool(args.get("full", False)),
        dry_run=bool(args.get("dry_run", False)),
    ),
}


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    if name not in HANDLERS:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        result = HANDLERS[name](arguments or {})
        return {"ok": True, "result": result}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def list_tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "workflow_go",
            "description": "Run bounded GO mode (GO, GO DEEP, GO VERIFY, GO AUDIT, GO SHIP)",
            "inputSchema": {
                "type": "object",
                "properties": {"mode": {"type": "string", "default": "GO"}},
            },
        },
        {
            "name": "workflow_git_ship",
            "description": "Confidence-gated git ship pipeline (dry-run by default)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "dry_run": {"type": "boolean", "default": True},
                    "session_id": {"type": "string"},
                },
            },
        },
        {
            "name": "auto_intake",
            "description": "Drain intake_queue.jsonl into beads",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "dry_run": {"type": "boolean", "default": False},
                    "limit": {"type": "integer"},
                    "session_id": {"type": "string"},
                },
            },
        },
        {
            "name": "poll_inbox",
            "description": "Poll Chromatic Inbox Harness SQLite into intake queue",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "dry_run": {"type": "boolean", "default": False},
                    "limit": {"type": "integer", "default": 20},
                    "session_id": {"type": "string"},
                },
            },
        },
        {
            "name": "intake_queue_list",
            "description": "List queued items in repo intake_queue.jsonl",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "beads_ready",
            "description": "Run bd ready — show unblocked beads issues",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "check_agent_operations",
            "description": "Verify mandatory harness docs and guardrails",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "validate_intake_loop",
            "description": "Validate P0 intake close-loop contract",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "parallel_health",
            "description": "Report concurrent session health (sessions, locks, orphaned worktrees)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prune": {"type": "boolean", "default": False},
                },
            },
        },
        {
            "name": "session_guard",
            "description": "Run unified cross-surface session automation (boot + token governance)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "surface": {"type": "string", "default": "mcp"},
                    "invoked_by": {"type": "string", "default": "automation"},
                    "force": {"type": "boolean", "default": False},
                    "full": {"type": "boolean", "default": False},
                    "dry_run": {"type": "boolean", "default": False},
                },
            },
        },
    ]
