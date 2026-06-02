#!/usr/bin/env python3
"""Provision and optionally open a parallel VS Code session worktree."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from common_harness import run_safe  # noqa: E402

WORKTREE_SCRIPT = REPO / "scripts" / "session_worktree.py"
ACTIVE_SCRIPT = REPO / "scripts" / "active_sessions.py"
LOCKS_DIR = REPO / ".agents" / "locks"


def _clean_argv(argv: list[str]) -> list[str]:
    # Ignore accidental placeholder args (for example ".") from shell/task wrappers.
    return [arg for arg in argv if arg.strip() != "."]


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = run_safe(cmd, cwd=REPO, timeout=120)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _vscode_cmd() -> str:
    for candidate in ("code-insiders", "code-insiders.cmd", "code", "code.cmd"):
        if shutil.which(candidate):
            return candidate
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch a parallel VS Code worktree session")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--invoked-by", default="vscode")
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--no-open", action="store_true", help="Do not open a new VS Code window")
    args = parser.parse_args(_clean_argv(list(argv if argv is not None else sys.argv[1:])))

    session_id = args.session_id.strip() or f"parallel-{uuid.uuid4().hex[:10]}"

    code, out, err = _run([sys.executable, str(WORKTREE_SCRIPT), "ensure", session_id, "--ref", args.ref])
    if code != 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "failed to provision worktree",
                    "exit_code": code,
                    "stdout": out[-4000:],
                    "stderr": err[-2000:],
                },
                indent=2,
            )
        )
        return code or 1

    try:
        ensure_payload = json.loads(out or "{}")
    except json.JSONDecodeError:
        ensure_payload = {}

    worktree_path = str(ensure_payload.get("worktree_path", ""))
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = str((LOCKS_DIR / f"{session_id}.lock").resolve())

    code, out, err = _run(
        [
            sys.executable,
            str(ACTIVE_SCRIPT),
            "start",
            "--invoked-by",
            args.invoked_by,
            "--session-id",
            session_id,
            "--worktree-path",
            worktree_path,
            "--lock-path",
            lock_path,
        ]
    )
    if code != 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "failed to register active session",
                    "exit_code": code,
                    "stdout": out[-4000:],
                    "stderr": err[-2000:],
                },
                indent=2,
            )
        )
        return code or 1

    opened = False
    open_error = ""
    if not args.no_open and worktree_path:
        cmd = _vscode_cmd()
        if cmd:
            proc = run_safe([cmd, "-n", worktree_path], cwd=REPO, timeout=30)
            opened = proc.returncode == 0
            if not opened:
                open_error = (proc.stderr or proc.stdout or "failed to open VS Code")[-1000:]
        else:
            open_error = "VS Code CLI not found (code/code-insiders)"

    print(
        json.dumps(
            {
                "ok": True,
                "session_id": session_id,
                "worktree_path": worktree_path,
                "lock_path": lock_path,
                "opened_vscode": opened,
                "open_error": open_error,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
