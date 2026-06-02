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
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_RUNTIME = _REPO / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))
sys.path.insert(0, str(_REPO / "scripts"))

from common_harness import run_safe  # noqa: E402

_PUSH_RE = re.compile(r"\bgit\s+push\b")
_PR_RE = re.compile(r"\bgh\s+pr\s+create\b")
_FORCE_RE = re.compile(r"(\s-f\b|--force\b|--force-with-lease\b|\s\+[\w/]+:)")


def _current_branch(cwd: Path | None = None) -> str:
    r = run_safe(
        ["git", "branch", "--show-current"],
        cwd=cwd if cwd is not None else _REPO,
        timeout=10,
    )
    return (r.stdout or "").strip()


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

    # Strip quoted segments before matching so a literal "git push" / "gh pr create"
    # inside a quoted argument (e.g. a commit message or a gh-api reply body) does not
    # trigger the gate. We only want the actual command tokens.
    unquoted = re.sub(r"'[^']*'|\"[^\"]*\"", " ", command)
    is_pr = bool(_PR_RE.search(unquoted))
    is_push = bool(_PUSH_RE.search(unquoted))
    if not (is_pr or is_push):
        return 0

    # Determine the effective working directory for the git/gh probes.
    # A leading `cd <path> &&` changes where the git/gh command ACTUALLY runs, so it
    # WINS over the shell's starting cwd. Priority: (1) leading `cd <path>` (resolved
    # against payload cwd if relative), (2) payload cwd, (3) _REPO.
    payload_cwd: Path | None = None
    _ti = payload.get("tool_input") or payload.get("toolInput") or {}
    raw_cwd = payload.get("cwd") or (_ti.get("cwd") if isinstance(_ti, dict) else None)
    if raw_cwd:
        try:
            payload_cwd = Path(str(raw_cwd)).resolve()
        except (OSError, ValueError):
            payload_cwd = None

    effective_cwd: Path | None = None
    m = re.match(r"\s*cd\s+(['\"]?)([^'\"&|;]+)\1\s*&&", command)
    if m:
        try:
            target = Path(m.group(2).strip())
            if not target.is_absolute() and payload_cwd is not None:
                target = payload_cwd / target
            effective_cwd = target.resolve()
        except (OSError, ValueError):
            return 0  # fail-open: can't parse path
    elif payload_cwd is not None:
        effective_cwd = payload_cwd

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

    # Advisory by default: only the genuinely destructive cases (a push that would
    # overwrite remote commits) HARD-block. Duplicate-PR / in-flight-Actions / issue
    # ownership are surfaced as warnings, not blocks — a guard reasoning about external
    # state from a limited payload is false-positive-prone, and a false block stalls
    # real work. Set CHROMATIC_COLLISION_STRICT=1 to hard-block on any collision.
    _DESTRUCTIVE = {"non_fast_forward", "force_overwrite"}
    strict = os.environ.get("CHROMATIC_COLLISION_STRICT", "").strip() in (
        "1",
        "true",
        "yes",
    )
    blocking = [b for b in verdict.hard_blocks if strict or b["kind"] in _DESTRUCTIVE]
    advisory = [b for b in verdict.hard_blocks if b not in blocking]

    for w in list(verdict.soft_warnings) + advisory:
        print(f"[collision][warn] {w['kind']}: {w['detail']}", file=sys.stderr)

    if blocking and os.environ.get("CHROMATIC_ALLOW_COLLISION", "").strip() not in (
        "1",
        "true",
        "yes",
    ):
        reasons = "; ".join(b["detail"] for b in blocking)
        print(
            f"BLOCKED by GitHub session-collision guard: {reasons}. Override once with CHROMATIC_ALLOW_COLLISION=1.",
            file=sys.stderr,
        )
        return 2  # exit 2 → Claude Code blocks the tool, shows stderr to the model

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
