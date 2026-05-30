# Activity Log and Dual Backlog

## Purpose

Every bounded harness action (session boot, GO phase, git ship, epic/subagent wave) produces **recoverable logs** and, when blocked, **backlog items** split by who must act next.

Chat is not the audit trail. Use logs + beads + intake.

---

## Logs (three layers)

| Layer | Path | Use |
|-------|------|-----|
| Human-facing run history | `docs/workflows/WORKFLOW_RUN_LOG.jsonl` (local; seed in git) | GO/GIT decisions, summaries |
| Execution (never sampled) | `07_LOGS_AND_AUDIT/execution/execution.jsonl` | Recovery, idempotency |
| Trace stub | `07_LOGS_AND_AUDIT/traces/traces.jsonl` | Diagnostics |
| Decision | `07_LOGS_AND_AUDIT/decisions/decision_log.jsonl` | Confidence gates |

`log_activity()` writes the workflow log and mirrors into two-log via [`append_run_log`](../workflows/TWO_LOG_AUDIT.md).

**Do not commit** runtime growth of `WORKFLOW_RUN_LOG.jsonl` — use the tracked seed file only in PRs.

---

## Standard event types

| `event_type` | When |
|--------------|------|
| `session.boot` | After successful `session_boot_automation.py` |
| `epic.start` | Epic / parent bead work begins |
| `phase.complete` | Bounded phase finished (session end, subagent wave) |
| `subagent.dispatch` | Parallel agent wave started |
| `git.failed` | `workflow_git` step failed |

Execution rows use `event_type` like `activity.session.boot` (see [TWO_LOG_AUDIT.md](../workflows/TWO_LOG_AUDIT.md)).

---

## Dual backlog lanes

One `bd` database; filter by **title prefix** and **description** line:

| Lane | Who acts | Title prefix | Description |
|------|----------|--------------|-------------|
| `agent` | Automation / agent | `[agent]` | First line: `lane: agent` |
| `human` | You (MCP, secrets, policy) | `[human]` | First line: `lane: human` |
| `review` | You approve before merge | `[review]` | First line: `lane: review` |

Intake entries may set top-level `lane` (optional). `auto_intake` applies prefix + description when creating beads.

### Commands

```bash
bd ready                                    # all ready work
python scripts/bd_ready_by_lane.py --lane agent
python scripts/bd_ready_by_lane.py --lane human
python scripts/bd_ready_by_lane.py --lane review
```

---

## When to enqueue intake

| Situation | Lane | Action |
|-----------|------|--------|
| Git commit/push/rebase failed | `human` (default) | `git_triage` → digest + intake `follow_up` |
| Unstaged generated files (.beads, inventory) | `agent` optional + `human` if blocked | Agent may suggest restore; human if policy unclear |
| Self-heal decomposition | `agent` | `workflow_go` 50–69 band → scout/worker follow-ups |
| Secrets in diff | `human` | Halt; never auto-commit |

Log-only (no intake): successful `phase.complete`, `session.boot`, dry-run GO.

---

## Git failure classes

| Class | Typical signal | Self-heal |
|-------|----------------|-----------|
| `unstaged_generated` | "unstaged changes" + `.beads` / `inventory` | Agent follow-up: restore or gitignore |
| `rebase_blocked` | "cannot pull with rebase" | Split digest into child beads |
| `commit_hook` | pre-commit / pre-push failed | Agent: fix tests in scope |
| `push_rejected` | remote rejected | Human |
| `test_fail` | pytest in hook output | Agent if scoped |
| `secrets` | secret path in diff | Human |
| `unknown` | other | Human + digest |

Digest path: `12_HANDOFFS/sessions/git-triage-<timestamp>.md` (≤500 words, handoff packet shape).

---

## Agent obligations (Cursor / Claude)

At **session end** or **epic phase boundary**:

```bash
python scripts/log_agent_activity.py log \
  --event phase.complete \
  --bead-id <id> \
  --lane agent \
  --summary "What finished; what is next"
```

On **git failure** (or after failed `workflow_git ship`):

```bash
python scripts/git_triage.py --from-log
python scripts/auto_intake.py --dry-run   # inspect queue
```

---

## Smoke verification

```bash
python scripts/log_agent_activity.py log --event phase.complete --bead-id chromatic-harness-v2-15x --lane agent --summary "smoke"
python scripts/workflow_git.py plan --confidence 90 --verifier approve --tests-passed
python -m pytest tests/test_activity_log.py tests/test_git_triage.py tests/test_two_log_audit.py -q
python scripts/bd_ready_by_lane.py --lane human
python scripts/check_agent_operations.py
```

---

## Related

- [INTAKE_QUEUE.md](../INTAKE_QUEUE.md)
- [TWO_LOG_AUDIT.md](../workflows/TWO_LOG_AUDIT.md)
- [HANDOFF_PACKET_SCHEMA.md](HANDOFF_PACKET_SCHEMA.md)
- [AGENT_OPERATIONS.md](../../AGENT_OPERATIONS.md)
