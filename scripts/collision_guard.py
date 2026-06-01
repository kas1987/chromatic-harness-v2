#!/usr/bin/env python3
"""collision_guard.py — preflight against multi-agent collisions (bead gl6t).

Answers, before you start mutating: "Is it safe to work here, or am I about to
collide with another agent / LLM session?" Emits pass/warn/fail per check plus
concrete advice. Read-only — it inspects git + beads, never mutates.

Checks:
  named_branch      — not working directly on the shared session/main branch.
  worktree_isolation— working inside a dedicated worktree (recommended) OR the
                      main checkout with no other active worktrees on your files.
  bead_claimed      — (with --bead ID) the target bead has an assignee; an
                      unclaimed bead must be claimed before work begins.
  no_branch_sharing — no other worktree currently has the same branch checked out.
  clean_index       — no in-progress merge / unresolved conflicts in this checkout.

Exit code: 0 if no FAIL; 1 if any hard-fail check fails (so it can gate a
session-start / pre-commit hook).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from common_harness import run_safe  # noqa: E402

SHARED_BRANCH_MARKERS = ("session/", "main", "master")
HARD_FAIL = {"clean_index", "no_branch_sharing"}


@dataclass
class Check:
    name: str
    status: str  # pass | warn | fail
    message: str
    advice: str = ""


def _git(args: list[str], timeout: int = 15) -> tuple[int, str]:
    # run_safe reaps the process tree on timeout (returns rc=124) and returns
    # rc=1 on spawn error — it never raises, so no try/except is needed here.
    r = run_safe(["git", *args], cwd=REPO, timeout=timeout)
    return r.returncode, (r.stdout or "").strip()


def current_branch() -> str:
    _, out = _git(["branch", "--show-current"])
    return out.strip()


def list_worktrees() -> list[dict]:
    """Parse `git worktree list --porcelain` into [{path, branch}]."""
    code, out = _git(["worktree", "list", "--porcelain"])
    if code != 0:
        return []
    trees: list[dict] = []
    cur: dict = {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur:
                trees.append(cur)
            cur = {"path": line[len("worktree ") :].strip()}
        elif line.startswith("branch "):
            cur["branch"] = line[len("branch ") :].strip().replace("refs/heads/", "")
    if cur:
        trees.append(cur)
    return trees


# ── Pure check builders (testable) ───────────────────────────────────────────


def check_named_branch(branch: str) -> Check:
    if not branch:
        return Check("named_branch", "warn", "detached HEAD", "checkout a named feature branch before working")
    if any(branch == m or branch.startswith(m) for m in SHARED_BRANCH_MARKERS):
        return Check(
            "named_branch",
            "fail",
            f"on shared branch '{branch}'",
            "create a per-issue feature branch (one PR per issue) so others don't collide",
        )
    return Check("named_branch", "pass", f"on feature branch '{branch}'")


def check_worktree_isolation(repo_path: Path, worktrees: list[dict]) -> Check:
    main_path = worktrees[0]["path"] if worktrees else str(repo_path)
    in_worktree = str(repo_path).replace("\\", "/") != str(main_path).replace("\\", "/")
    active_others = [w for w in worktrees[1:] if w.get("branch")]
    if in_worktree:
        return Check("worktree_isolation", "pass", "working inside a dedicated worktree")
    if active_others:
        return Check(
            "worktree_isolation",
            "warn",
            f"on main checkout with {len(active_others)} other active worktree(s)",
            "prefer a dedicated `git worktree` for this task to avoid file/stash collisions",
        )
    return Check("worktree_isolation", "pass", "main checkout, no competing worktrees")


def check_branch_sharing(branch: str, worktrees: list[dict]) -> Check:
    if not branch:
        return Check("no_branch_sharing", "pass", "no branch to share (detached)")
    holders = [w["path"] for w in worktrees if w.get("branch") == branch]
    if len(holders) > 1:
        return Check(
            "no_branch_sharing",
            "fail",
            f"branch '{branch}' checked out in {len(holders)} worktrees",
            "two checkouts on one branch WILL collide; move one to its own branch",
        )
    return Check("no_branch_sharing", "pass", f"branch '{branch}' is exclusive to this checkout")


def check_clean_index() -> Check:
    if (REPO / ".git" / "MERGE_HEAD").exists():
        return Check(
            "clean_index",
            "fail",
            "merge in progress (MERGE_HEAD present)",
            "resolve or `git merge --abort` before working",
        )
    code, out = _git(["diff", "--name-only", "--diff-filter=U"])
    unresolved = [ln for ln in out.splitlines() if ln.strip() and not ln.startswith("warning:")]
    if unresolved:
        return Check(
            "clean_index", "fail", f"{len(unresolved)} unresolved conflict(s)", "resolve conflicts before committing"
        )
    return Check("clean_index", "pass", "no merge/conflict in progress")


def check_bead_claimed(bead_id: str) -> Check:
    bd = shutil.which("bd") or shutil.which("bd.cmd")
    if not bd:
        return Check("bead_claimed", "warn", "bd not on PATH; cannot verify claim", "")
    try:
        r = run_safe([bd, "show", bead_id, "--json"], cwd=REPO, timeout=20)
        if r.returncode != 0 or not r.stdout.strip():
            return Check("bead_claimed", "warn", f"bead {bead_id} not found", "")
        data = json.loads(r.stdout)
        if isinstance(data, list):
            data = data[0] if data else {}
        assignee = str(data.get("assignee") or "").strip()
        status = str(data.get("status") or "").lower()
        if assignee:
            return Check("bead_claimed", "pass", f"{bead_id} claimed by '{assignee}' (status={status})")
        return Check(
            "bead_claimed",
            "warn",
            f"{bead_id} is UNCLAIMED (status={status})",
            "run `bd update " + bead_id + " --claim` before working, or pick an unclaimed bead / become a reviewer",
        )
    except json.JSONDecodeError as exc:
        # run_safe absorbs timeout/OSError (returns sentinel codes handled above);
        # malformed bd JSON is the only remaining raisable error here.
        return Check("bead_claimed", "warn", f"claim check failed: {exc}", "")


def run_guard(bead_id: str = "") -> dict:
    branch = current_branch()
    worktrees = list_worktrees()
    checks = [
        check_named_branch(branch),
        check_worktree_isolation(REPO, worktrees),
        check_branch_sharing(branch, worktrees),
        check_clean_index(),
    ]
    if bead_id:
        checks.append(check_bead_claimed(bead_id))

    counts = {"pass": 0, "warn": 0, "fail": 0}
    for c in checks:
        counts[c.status] = counts.get(c.status, 0) + 1
    hard_fail = any(c.status == "fail" and c.name in HARD_FAIL for c in checks)
    # any FAIL is blocking; named_branch fail is also blocking (shared-branch work)
    blocking = hard_fail or any(c.status == "fail" for c in checks)
    overall = "fail" if blocking else ("warn" if counts["warn"] else "pass")
    return {
        "branch": branch,
        "worktree_count": len(worktrees),
        "overall": overall,
        "counts": counts,
        "checks": [asdict(c) for c in checks],
    }


def summarize() -> dict:
    """Fail-open compact summary for the closeout report / meta-gate."""
    try:
        result = run_guard()
        return {
            "status": "ok",
            "overall": result["overall"],
            "branch": result["branch"],
            "worktree_count": result["worktree_count"],
            "counts": result["counts"],
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "overall": None}


def main() -> int:
    ap = argparse.ArgumentParser(description="Multi-agent collision preflight guard (bead gl6t)")
    ap.add_argument("--bead", default="", help="also verify this bead is claimed before work")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of the human summary")
    args = ap.parse_args()

    result = run_guard(args.bead)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"collision-guard: {result['overall'].upper()}  (branch={result['branch']}, worktrees={result['worktree_count']})"
        )
        for c in result["checks"]:
            line = f"  [{c['status'].upper():4s}] {c['name']}: {c['message']}"
            if c["status"] != "pass" and c.get("advice"):
                line += f"\n         -> {c['advice']}"
            print(line)
    return 1 if result["overall"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
