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


def _current_branch(cwd: Path | None = None) -> str:
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(cwd) if cwd is not None else str(_REPO),
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

    # Determine the effective working directory for the git/gh probes.
    # Priority: (1) explicit payload cwd field, (2) leading `cd <path> &&`, (3) _REPO.
    effective_cwd: Path | None = None

    # Check for explicit cwd in the payload (Claude Code sets this on Bash calls).
    payload_cwd = payload.get("cwd") or ((payload.get("tool_input") or {}).get("cwd"))
    if payload_cwd:
        try:
            effective_cwd = Path(str(payload_cwd)).resolve()
        except (OSError, ValueError):
            effective_cwd = None

    # Fall back to leading `cd <path> &&` detection.
    m = re.match(r"\s*cd\s+(['\"]?)([^'\"&|;]+)\1\s*&&", command)
    if m and effective_cwd is None:
        target = m.group(2).strip()
        try:
            effective_cwd = Path(target).resolve()
        except (OSError, ValueError):
            return 0  # fail-open: can't parse path

    # If the effective cwd is outside _REPO, fail-open: we can't reliably judge
    # collisions for an unrelated repo.
    if effective_cwd is not None:
        if effective_cwd != _REPO and _REPO not in effective_cwd.parents:
            return 0
    else:
        effective_cwd = _REPO

    try:
        from concurrency.github_collision import OPEN_PR, PUSH, check_github_collision

        verdict = check_github_collision(
            branch=_current_branch(effective_cwd),
            action=OPEN_PR if is_pr else PUSH,
            force=bool(_FORCE_RE.search(command)),
            cwd=str(effective_cwd),
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
