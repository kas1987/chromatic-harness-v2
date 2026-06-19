# Agent Control Loop & Queue Protocol

**Bead:** mc-rxu05 (CC #33)  
**Status:** Design v1.0  
**Date:** 2026-06-19

---

## Overview

The agent control loop is the execution backbone of the Chromatic Harness. It governs how long-running agents pick up work, process it, and report results — without requiring a human in the loop for routine task progression.

---

## Control Loop Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CONTROL LOOP                             │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────┐ │
│  │ DISPATCH │───▶│ CLAIM    │───▶│ EXECUTE  │───▶│REPORT │ │
│  │  QUEUE   │    │  GATE    │    │  ENGINE  │    │  OUT  │ │
│  └──────────┘    └──────────┘    └──────────┘    └───────┘ │
│        ▲                                              │      │
│        └──────────────── FEEDBACK ───────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Phases

**1. Dispatch** — Task enters the queue. Sources:
- `bd q` (quick capture from CLI)
- Hook-triggered dispatch (pre-push preflight, review-daemon findings)
- Multica autopilot cron (*/2 schedule)
- Manual `bd assign`

**2. Claim Gate** — Agent claims a task before executing:
- Checks task state = `ready`
- Sets state = `in_progress`, stamps `claimed_at`
- Writes lock entry to `.agents/registry/<agent-id>.json`
- If claim fails (already claimed), agent idles and polls

**3. Execute Engine** — Task runs in isolated context:
- Agent reads task spec from `bd show <id>`
- Executes against working directory
- Emits structured logs to `07_LOGS_AND_AUDIT/agent-events/`
- Hard timeout: 300s per task (configurable via `AGENT_TASK_TIMEOUT_S`)

**4. Report Out** — Task closes with structured result:
- `bd close --reason "<summary>"` on success
- `bd label add <id> blocked` + comment on blocker
- Appends result to `.agents/events/<task-id>.jsonl`

**5. Feedback Loop** — Closed tasks inform next dispatch:
- Token telemetry written to `07_LOGS_AND_AUDIT/token_governance/`
- Governance loop reads telemetry, adjusts routing weights
- Next `bd ready` poll uses updated priority ordering

---

## Queue Protocol

### Task States

```
PENDING → READY → IN_PROGRESS → CLOSED
                      │
                      └──→ BLOCKED (manual intervention required)
```

### Priority Ordering

Tasks surface from `bd ready` in this order:
1. `priority: critical` (P0)
2. `priority: high` (P1)
3. `priority: medium` (P2) — default
4. `priority: low` (P3)
5. Within same priority: FIFO by creation timestamp

### Claim Protocol (concurrency safety)

```json
// .agents/registry/<agent-id>.json
{
  "agent_id": "a5a8186d82a573ee4",
  "task_id": "mc-rxu05",
  "claimed_at": "2026-06-19T14:00:00Z",
  "context": "chromatic-harness-v2",
  "pid": 12345
}
```

Stale claims (no heartbeat for >600s) are released by the governance enforcer (`agent-dictator`).

### Queue Dispatch Format

```json
// .dispatch/<task-id>.json
{
  "task_id": "mc-rxu05",
  "title": "Design long-running agent control loop",
  "c_level": "C3",
  "priority": "P2",
  "context": "chromatic-harness-v2",
  "dispatched_at": "2026-06-19T13:00:00Z",
  "tags": ["architecture", "command-center"]
}
```

---

## Long-Running Agent Pattern

For tasks expected to exceed one interaction turn:

1. Agent writes a `CHECKPOINT` file to `.agents/checkpoints/<task-id>.json` every N steps
2. On resumption, agent reads checkpoint and continues from last confirmed state
3. Checkpoint format:
   ```json
   {"task_id": "mc-rxu05", "step": 3, "completed_steps": ["read", "plan"], "next": "write"}
   ```
4. Harness kernel sets `AGENT_CHECKPOINT_INTERVAL=5` (steps between writes)

---

## Governance Constraints

- No task may hold `in_progress` for >300s without a heartbeat write
- Agents must not self-assign tasks outside their registered C-level range
- All agent events must be written to the audit log before `bd close` is called
- `CLAUDE_PREFLIGHT_STRICT=1` blocks dispatch if governance files are missing

---

## Related

- `AGENT_GO_LOOP.md` — GO Loop skill activation and trigger injection
- `docs/SOPs/NATIVE_CLAUDE_RELAY_SOP.md` — relay for C3/C4 task dispatch
- `.agents/registry/` — live claim registry
