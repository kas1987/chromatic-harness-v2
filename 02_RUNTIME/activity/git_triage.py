"""Classify git failures and enqueue dual-backlog follow-ups with digest handoff."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from activity.lanes import normalize_lane
from activity.log import log_activity

FAILURE_CLASSES = frozenset(
    {
        "unstaged_generated",
        "rebase_blocked",
        "commit_hook",
        "push_rejected",
        "test_fail",
        "secrets",
        "unknown",
    }
)

_GENERATED_MARKERS = (
    ".beads/",
    "issues.jsonl",
    "inventory.snapshot",
    "PRE_SESSION_INVENTORY",
    "WORKFLOW_RUN_LOG",
    "latest.json",
)


@dataclass
class TriageResult:
    failure_class: str
    digest_path: str
    intake_ids: list[str] = field(default_factory=list)
    agent_intake_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_class": self.failure_class,
            "digest_path": self.digest_path,
            "intake_ids": self.intake_ids,
            "agent_intake_id": self.agent_intake_id,
        }


def classify_git_failure(stderr: str, step_name: str = "") -> str:
    """Map git stderr/stdout to a failure class."""
    text = f"{step_name}\n{stderr}".lower()
    if "secret" in text or ".env" in text and "commit" in text:
        return "secrets"
    if "pytest" in text or "pre-push" in text and "fail" in text:
        return "test_fail"
    if "pre-commit" in text or "hook" in text and "fail" in text:
        return "commit_hook"
    if "rejected" in text or "permission denied" in text and "push" in text:
        return "push_rejected"
    if any(m in text for m in _GENERATED_MARKERS):
        return "unstaged_generated"
    if "cannot pull with rebase" in text or "unstaged changes" in text:
        return "rebase_blocked"
    if "unstaged" in text or "would be overwritten" in text:
        return "unstaged_generated"
    if "conflict" in text or "merge" in text and "fail" in text:
        return "rebase_blocked"
    return "unknown"


def _failed_steps_summary(steps: list[dict[str, Any]]) -> tuple[str, str]:
    parts: list[str] = []
    for step in steps:
        if step.get("status") != "failed":
            continue
        cmd = step.get("cmd", step.get("step", "?"))
        err = step.get("stderr", step.get("reason", ""))
        parts.append(f"cmd: {cmd}\n{err}")
    combined = "\n---\n".join(parts)
    step_name = ""
    if steps:
        failed = [s for s in steps if s.get("status") == "failed"]
        if failed:
            cmd = failed[-1].get("cmd", [])
            step_name = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
    return combined, step_name


def _write_digest(
    repo_root: Path,
    *,
    failure_class: str,
    bead_id: str,
    steps: list[dict[str, Any]],
    stderr_summary: str,
) -> Path:
    sessions = repo_root / "12_HANDOFFS" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    path = sessions / f"git-triage-{ts}.md"
    bullets = _digest_bullets(failure_class, stderr_summary)
    body = f"""# Git triage — {failure_class}

## Objective
Resolve git pipeline failure without losing beads or generated-file policy.

## Decision
Classified as `{failure_class}`. Primary lane: human unless agent follow-up was enqueued.

## Summary
Bead: `{bead_id or "none"}`
Failed step output (truncated):

```
{stderr_summary[:2500]}
```

## Evidence refs
- `docs/governance/ACTIVITY_LOG_AND_DUAL_BACKLOG.md`
- Last workflow log: `docs/workflows/WORKFLOW_RUN_LOG.jsonl`

## Risks
- Do not force-push main/master.
- Do not commit secrets or `.env`.

## Blockers
{chr(10).join(f"- {b}" for b in bullets)}

## Next action
1. Read this digest.
2. Run `python scripts/bd_ready_by_lane.py --lane human` (or agent).
3. `python scripts/auto_intake.py` after reviewing queue.

## Suggested child tasks
{chr(10).join(f"- {b}" for b in bullets)}

## Confidence
50 — needs review before retry ship.
"""
    path.write_text(body[:8000], encoding="utf-8")
    return path


def _digest_bullets(failure_class: str, stderr_summary: str) -> list[str]:
    if failure_class == "unstaged_generated":
        return [
            "Restore or gitignore generated paths (.beads/issues.jsonl, inventory snapshots)",
            "Re-run git status; commit only intentional source changes",
            "Re-run workflow_git plan before ship --execute",
        ]
    if failure_class == "rebase_blocked":
        return [
            "Stash or commit intentional work; resolve rebase blockers",
            "Split large conflict into per-file beads",
        ]
    if failure_class == "commit_hook":
        return [
            "Run pytest locally on failing modules",
            "Fix hook findings; new commit (no amend if pushed)",
        ]
    if failure_class == "test_fail":
        return [
            "Identify failing test file from hook output",
            "Scope fix bead to one module",
        ]
    if failure_class == "secrets":
        return [
            "Remove secret paths from index; rotate if committed",
            "Human approval required before any push",
        ]
    if failure_class == "push_rejected":
        return [
            "Check remote permissions and branch protection",
            "Human: open PR manually if automation blocked",
        ]
    return [
        "Inspect stderr in digest",
        "Create scoped follow-up beads from suggested child tasks",
    ]


def triage_git_failure(
    repo_root: Path,
    *,
    steps: list[dict[str, Any]],
    bead_id: str = "",
    lane: str = "human",
    stderr: str = "",
) -> TriageResult:
    """Write digest, log git.failed, enqueue human (+ optional agent) intake."""
    import sys

    runtime = Path(__file__).resolve().parents[1]
    if str(runtime) not in sys.path:
        sys.path.insert(0, str(runtime))

    from intake.queue import append_entry  # noqa: E402

    stderr_summary, step_name = _failed_steps_summary(steps)
    if stderr and stderr not in stderr_summary:
        stderr_summary = f"{stderr_summary}\n{stderr}".strip()

    failure_class = classify_git_failure(stderr_summary, step_name)
    digest_path = _write_digest(
        repo_root,
        failure_class=failure_class,
        bead_id=bead_id,
        steps=steps,
        stderr_summary=stderr_summary,
    )

    log_activity(
        repo_root,
        event_type="git.failed",
        bead_id=bead_id,
        lane=lane,
        decision="failed",
        error=stderr_summary[:2000],
        summary=f"Git triage: {failure_class}",
        intake_on_failure=False,
        handoff={"digest_path": str(digest_path.relative_to(repo_root))},
    )

    resolved_lane = normalize_lane(lane)
    intake_ids: list[str] = []

    human_id = f"gt-{failure_class}-{datetime.now(timezone.utc).strftime('%H%M%S')}"[:80]
    append_entry(
        {
            "id": human_id,
            "source": "workflow",
            "kind": "follow_up",
            "status": "queued",
            "title": f"Git triage [{failure_class}]: review digest",
            "goal": _digest_bullets(failure_class, stderr_summary)[0],
            "priority": "P1",
            "type": "task",
            "tier": 2,
            "lane": resolved_lane,
            "bead_id": bead_id,
            "context": {
                "failure_class": failure_class,
                "digest_path": str(digest_path.relative_to(repo_root)),
                "event_type": "git.failed",
                "parent_bead_id": bead_id,
            },
        },
        repo_root=repo_root,
    )
    intake_ids.append(human_id)

    agent_id = ""
    if failure_class == "unstaged_generated":
        agent_id = f"gt-agent-{datetime.now(timezone.utc).strftime('%H%M%S')}"[:80]
        append_entry(
            {
                "id": agent_id,
                "source": "workflow",
                "kind": "follow_up",
                "status": "queued",
                "title": "Restore generated files or update gitignore before rebase",
                "goal": "- git restore generated paths\n- Re-run workflow_git plan",
                "priority": "P2",
                "type": "task",
                "tier": 1,
                "lane": "agent",
                "bead_id": bead_id,
                "context": {
                    "failure_class": failure_class,
                    "digest_path": str(digest_path.relative_to(repo_root)),
                    "self_heal": True,
                },
            },
            repo_root=repo_root,
        )
        intake_ids.append(agent_id)

    elif failure_class in ("rebase_blocked", "secrets"):
        for i, bullet in enumerate(_digest_bullets(failure_class, stderr_summary)[:3]):
            fid = f"gt-split-{i}-{datetime.now(timezone.utc).strftime('%H%M%S')}"[:80]
            append_entry(
                {
                    "id": fid,
                    "source": "workflow",
                    "kind": "follow_up",
                    "status": "queued",
                    "title": bullet[:120],
                    "goal": bullet,
                    "priority": "P1",
                    "type": "task",
                    "tier": 2,
                    "lane": resolved_lane,
                    "bead_id": bead_id,
                    "context": {
                        "failure_class": failure_class,
                        "digest_path": str(digest_path.relative_to(repo_root)),
                    },
                },
                repo_root=repo_root,
            )
            intake_ids.append(fid)

    return TriageResult(
        failure_class=failure_class,
        digest_path=str(digest_path.relative_to(repo_root)),
        intake_ids=intake_ids,
        agent_intake_id=agent_id,
    )
