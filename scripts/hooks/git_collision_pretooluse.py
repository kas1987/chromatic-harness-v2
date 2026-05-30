#!/usr/bin/env python3
"""PreToolUse hook: gate `git push` / `gh pr create` on GitHub session-collision.

Generalizes the workflow_git collision gate to *any* push path (raw Bash tool
calls, not just workflow_git ship). Reads the Claude Code PreToolUse payload from
stdin; if the Bash command is a push / PR-create, it runs the shared
``check_github_collision`` probe and **blocks on a hard collision** (exit 2, reason
on stderr). Soft warnings are printed but allowed.

Fail-open by construction: any parse/probe error, a non-matching command, or
``CHROMATIC_NO_COLLISION_HOOK=1`` → exit 0 (allow). Override a hard block once with
``CHROMATIC_ALLOW_COLLISION=1``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

_PUSH_RE = re.compile(r"\bgit\s+push\b")
_PR_RE = re.compile(r"\bgh\s+pr\s+create\b")
_FORCE_RE = re.compile(r"(\s-f\b|--force\b|--force-with-lease\b|\s\+[\w/]+:)")


def _current_branch() -> str:
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=_REPO,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return (r.stdout or "").strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def _extract_command(payload: dict) -> str:
    tool = payload.get("tool_name") or payload.get("toolName") or ""
    if tool and tool != "Bash":
        return ""
    ti = payload.get("tool_input") or payload.get("toolInput") or {}
    if isinstance(ti, dict):
        return str(ti.get("command") or "")
    return ""


def main() -> int:
    if os.environ.get("CHROMATIC_NO_COLLISION_HOOK", "").strip() in (
        "1",
        "true",
        "yes",
    ):
        return 0
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0  # fail-open: can't parse → allow

    command = _extract_command(payload)
    if not command:
        return 0

    is_pr = bool(_PR_RE.search(command))
    is_push = bool(_PUSH_RE.search(command))
    if not (is_pr or is_push):
        return 0

    # The probe reasons about _REPO (this repo). A command that `cd`s into a
    # *different* repo (e.g. the wiki) would be judged against the wrong repo, so
    # fail-open rather than false-block. Detect a leading `cd <path>` outside _REPO.
    m = re.match(r"\s*cd\s+(['\"]?)([^'\"&|;]+)\1\s*&&", command)
    if m:
        target = m.group(2).strip()
        try:
            if (
                Path(target).resolve() != _REPO
                and _REPO not in Path(target).resolve().parents
            ):
                return 0
        except (OSError, ValueError):
            return 0

    try:
        from concurrency.github_collision import OPEN_PR, PUSH, check_github_collision

        verdict = check_github_collision(
            branch=_current_branch(),
            action=OPEN_PR if is_pr else PUSH,
            force=bool(_FORCE_RE.search(command)),
        )
    except Exception:  # noqa: BLE001 — never break the tool call
        return 0

    for w in verdict.soft_warnings:
        print(f"[collision][warn] {w['kind']}: {w['detail']}", file=sys.stderr)

    if verdict.blocked and os.environ.get(
        "CHROMATIC_ALLOW_COLLISION", ""
    ).strip() not in ("1", "true", "yes"):
        reasons = "; ".join(b["detail"] for b in verdict.hard_blocks)
        print(
            "BLOCKED by GitHub session-collision guard: "
            f"{reasons}. Override once with CHROMATIC_ALLOW_COLLISION=1.",
            file=sys.stderr,
        )
        return 2  # exit 2 → Claude Code blocks the tool, shows stderr to the model

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
