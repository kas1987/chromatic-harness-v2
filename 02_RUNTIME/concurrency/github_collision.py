"""GitHub session-collision detection — soft/hard blocks before mutating GitHub.

The local ``session_lock`` serializes operations *within this machine's* sessions.
This module is its read-side complement: it inspects **remote GitHub state** so two
sessions (or a session and CI/another contributor) don't collide on the same branch,
PR, Action run, or issue.

Verdict model (mirrors the governance gate tiers):

* **hard block** — physically unsafe / duplicate-creating. The caller must stop unless
  the operator explicitly forces (and force is itself gated).
* **soft warning** — in-flight activity worth surfacing, but the action can proceed.

Detection is dependency-injected (``gh_runner`` / ``git_runner``) so it is fully
testable without a network. All probes **fail open**: if ``gh`` is unavailable or
errors, we emit a soft warning ("could not verify") rather than a hard block, so
offline/no-auth development is never bricked — the existing pre-push hook remains the
last line of defense.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable

Runner = Callable[[list[str]], "tuple[int, str]"]

# Actions that mutate shared GitHub state and therefore warrant a collision probe.
PUSH = "push"
OPEN_PR = "open_pr"
_VALID_ACTIONS = {PUSH, OPEN_PR}


def _default_runner(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


@dataclass
class CollisionVerdict:
    action: str
    branch: str
    base: str = ""
    force: bool = False
    hard_blocks: list[dict[str, str]] = field(default_factory=list)
    soft_warnings: list[dict[str, str]] = field(default_factory=list)

    @property
    def decision(self) -> str:
        if self.hard_blocks:
            return "block"
        if self.soft_warnings:
            return "warn"
        return "ok"

    @property
    def blocked(self) -> bool:
        return bool(self.hard_blocks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "branch": self.branch,
            "base": self.base,
            "force": self.force,
            "decision": self.decision,
            "hard_blocks": self.hard_blocks,
            "soft_warnings": self.soft_warnings,
        }


def _json_or_none(code: int, out: str) -> Any:
    if code != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _probe_open_pr(v: CollisionVerdict, gh: Runner) -> None:
    code, out = gh(
        [
            "gh",
            "pr",
            "list",
            "--head",
            v.branch,
            "--state",
            "open",
            "--json",
            "number,author,headRefName,url",
        ]
    )
    data = _json_or_none(code, out)
    if data is None:
        v.soft_warnings.append(
            {
                "kind": "gh_unverified",
                "detail": "could not verify open PRs (gh unavailable)",
            }
        )
        return
    if not data:
        return
    pr = data[0]
    num = pr.get("number")
    url = pr.get("url", "")
    if v.action == OPEN_PR:
        v.hard_blocks.append(
            {
                "kind": "duplicate_pr",
                "detail": f"PR #{num} already open for {v.branch}: {url}",
            }
        )
    else:  # push updates the existing PR — fine, but surface it
        v.soft_warnings.append(
            {"kind": "pr_in_flight", "detail": f"push updates open PR #{num}: {url}"}
        )


def _probe_actions(v: CollisionVerdict, gh: Runner) -> None:
    code, out = gh(
        [
            "gh",
            "run",
            "list",
            "--branch",
            v.branch,
            "--limit",
            "20",
            "--json",
            "databaseId,status,workflowName",
        ]
    )
    data = _json_or_none(code, out)
    if data is None:
        v.soft_warnings.append(
            {
                "kind": "gh_unverified",
                "detail": "could not verify Action runs (gh unavailable)",
            }
        )
        return
    active = [
        r
        for r in data
        if str(r.get("status", "")).lower()
        in {"in_progress", "queued", "waiting", "pending"}
    ]
    if not active:
        return
    names = ", ".join(sorted({str(r.get("workflowName", "?")) for r in active}))
    detail = f"{len(active)} Action run(s) in flight on {v.branch}: {names}"
    if v.force:
        v.hard_blocks.append({"kind": "actions_force_conflict", "detail": detail})
    else:
        v.soft_warnings.append({"kind": "actions_in_flight", "detail": detail})


def _probe_remote_ahead(v: CollisionVerdict, git: Runner) -> None:
    # Fetch quietly, then count commits on the remote branch not present locally.
    git(["git", "fetch", "--quiet", "origin", v.branch])
    code, out = git(["git", "rev-list", "--count", f"HEAD..origin/{v.branch}"])
    if code != 0:
        # No remote branch yet (first push) or fetch failed — not a collision.
        return
    try:
        ahead = int(out.strip() or "0")
    except ValueError:
        return
    if ahead > 0:
        detail = f"origin/{v.branch} is {ahead} commit(s) ahead of HEAD (another session pushed)"
        if v.force:
            v.hard_blocks.append({"kind": "force_overwrite", "detail": detail})
        else:
            v.hard_blocks.append({"kind": "non_fast_forward", "detail": detail})


def _probe_issue_ownership(
    v: CollisionVerdict, bead_id: str, session_id: str, gh: Runner
) -> None:
    if not bead_id:
        return
    code, out = gh(
        [
            "gh",
            "issue",
            "list",
            "--search",
            bead_id,
            "--state",
            "open",
            "--json",
            "number,title,assignees,url",
        ]
    )
    data = _json_or_none(code, out)
    if not data:
        return
    for issue in data:
        assignees = [a.get("login", "") for a in (issue.get("assignees") or [])]
        if assignees:
            v.soft_warnings.append(
                {
                    "kind": "issue_owned",
                    "detail": (
                        f"issue #{issue.get('number')} ({bead_id}) assigned to "
                        f"{', '.join(assignees)}: {issue.get('url', '')}"
                    ),
                }
            )


def check_github_collision(
    *,
    branch: str,
    action: str,
    base: str = "",
    bead_id: str = "",
    session_id: str = "",
    force: bool = False,
    gh_runner: Runner | None = None,
    git_runner: Runner | None = None,
) -> CollisionVerdict:
    """Probe remote GitHub state for collisions before ``action`` on ``branch``."""
    if action not in _VALID_ACTIONS:
        raise ValueError(f"action must be one of {_VALID_ACTIONS}, got {action!r}")
    gh = gh_runner or _default_runner
    git = git_runner or _default_runner
    v = CollisionVerdict(action=action, branch=branch, base=base, force=force)

    _probe_remote_ahead(v, git)
    _probe_open_pr(v, gh)
    _probe_actions(v, gh)
    _probe_issue_ownership(v, bead_id, session_id, gh)
    return v
