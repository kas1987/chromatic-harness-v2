#!/usr/bin/env python3
"""Manage per-session git worktrees for concurrent Harness sessions."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKTREES_DIR = REPO / ".worktrees"


def _clean_argv(argv: list[str]) -> list[str]:
    # Ignore accidental placeholder args (for example ".") from shell/task wrappers.
    return [arg for arg in argv if arg.strip() != "."]


def _safe_name(raw: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", raw.strip())
    return name.strip("-._") or "session"


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def cmd_ensure(session_id: str, ref: str = "HEAD") -> int:
    WORKTREES_DIR.mkdir(parents=True, exist_ok=True)
    path = WORKTREES_DIR / _safe_name(session_id)
    if path.exists():
        print(json.dumps({"ok": True, "worktree_path": str(path), "created": False}, indent=2))
        return 0

    code, out, err = _run(["git", "worktree", "add", "--detach", str(path), ref])
    if code != 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "failed to create worktree",
                    "exit_code": code,
                    "stdout": out[-4000:],
                    "stderr": err[-2000:],
                },
                indent=2,
            )
        )
        return code or 1

    print(json.dumps({"ok": True, "worktree_path": str(path), "created": True}, indent=2))
    return 0


def cmd_remove(session_id: str) -> int:
    path = WORKTREES_DIR / _safe_name(session_id)
    if not path.exists():
        print(json.dumps({"ok": True, "worktree_path": str(path), "removed": False}, indent=2))
        return 0

    code, out, err = _run(["git", "worktree", "remove", "--force", str(path)])
    if code != 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "failed to remove worktree",
                    "exit_code": code,
                    "stdout": out[-4000:],
                    "stderr": err[-2000:],
                },
                indent=2,
            )
        )
        return code or 1

    print(json.dumps({"ok": True, "worktree_path": str(path), "removed": True}, indent=2))
    return 0


def cmd_list() -> int:
    code, out, err = _run(["git", "worktree", "list", "--porcelain"])
    if code != 0:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "failed to list worktrees",
                    "exit_code": code,
                    "stdout": out[-4000:],
                    "stderr": err[-2000:],
                },
                indent=2,
            )
        )
        return code or 1

    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in out.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        parts = line.split(" ", 1)
        key = parts[0]
        value = parts[1] if len(parts) > 1 else ""
        if key == "worktree":
            current["worktree"] = value
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value
        else:
            current[key.lower()] = value
    if current:
        entries.append(current)

    print(json.dumps({"ok": True, "count": len(entries), "items": entries}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage Harness session worktrees")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ensure = sub.add_parser("ensure", help="Ensure a session worktree exists")
    p_ensure.add_argument("session_id")
    p_ensure.add_argument("--ref", default="HEAD")

    p_remove = sub.add_parser("remove", help="Remove a session worktree")
    p_remove.add_argument("session_id")

    sub.add_parser("list", help="List git worktrees")

    args = parser.parse_args(_clean_argv(list(argv if argv is not None else sys.argv[1:])))

    if args.cmd == "ensure":
        return cmd_ensure(args.session_id, ref=args.ref)
    if args.cmd == "remove":
        return cmd_remove(args.session_id)
    if args.cmd == "list":
        return cmd_list()

    print(json.dumps({"ok": False, "error": f"unknown command: {args.cmd}"}, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())