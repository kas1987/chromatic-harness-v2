# Review Dispatch Playbook

## Purpose

Route queued review findings to the correct agent or subagent with bounded scope.

## Dispatch Requirements

Every dispatch must include:

- task ID
- source finding ID
- PR link/comment link
- owner agent
- allowed files
- forbidden files
- acceptance checks
- confidence score
- risk level
- stop conditions

## Agent Routing

| Finding Type | Agent |
|---|---|
| security | Sentinel |
| test_failure | Auditor |
| lint_style | Janitor |
| docs | Archivist |
| architecture | Archivist / Auditor |
| bug_fix | Sentinel |
| repo_hygiene | Janitor |
| unclear | Auditor |

## Dispatch Rule

Only dispatch `ready` items unless the user explicitly requests blocked/planned review.

## Stop Conditions

- Confidence below 75 for mutation work.
- Allowed files are empty for code mutation.
- Human gate required.
- PR branch already has an active mutation lock.

## Running the Dispatcher (live loop)

`scripts/dispatch_review_work.py` selects `ready` queue items, acquires the PR branch
lock, renders a mission packet, and writes an `agent_dispatch` record. With `--emit-beads`
it also registers each dispatched finding as a bead so the work enters the normal
`bd ready` loop and the GitHub-issue mirror (`AGENT_HANDOFF_QUEUE.md`).

```bash
# Dispatch up to 3 ready findings into the live bead loop:
python scripts/dispatch_review_work.py --limit 3 --emit-beads

# Inspect what would be dispatched without acting:
python scripts/dispatch_review_work.py --limit 10 --dry-run
```

Bead creation is idempotent (an item already carrying `bead_id` is not re-created) and
degrades gracefully: if `bd` is unavailable the dispatcher still produces the mission
packet and dispatch record, just without a bead. After an agent finishes, close the loop
with `scripts/post_review_resolution.py` (requires files + validation evidence) and
`bd close <bead-id>`.
