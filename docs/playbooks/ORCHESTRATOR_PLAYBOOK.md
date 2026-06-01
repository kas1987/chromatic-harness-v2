# Orchestrator Playbook

> Issue #81 / NW-RG-081. The orchestration contract enforced by `scripts/go_mode.py`.

## Purpose

Select, score, dispatch, and monitor the next unit of harness work — one task at
a time, deterministically, with a recorded rationale.

## Responsibilities

| Step | Mechanism |
|---|---|
| Read queue | `load_queue_from_bd()` (`bd ready --json`) or `--queue-file` |
| Select unblocked work | `select_next()` — exclude done/blocked, prefer ready/P0/id |
| Generate mission packet | `build_mission_packet()` — all required fields |
| Enforce confidence gate | `score_confidence()` + `dispatch_allowed()` |
| Assign owner agent | from queue item `owner_agent` / `secondary_agent` |
| Record result | `write_artifact()` → `07_LOGS_AND_AUDIT/go_mode/latest.json` |

## Human gate rules

The orchestrator **plans and dispatches; it never mutates, commits, or merges.**
A human (or an explicitly-dispatched executor agent) performs the actual change.
Human approval is required to:

- proceed when confidence is in `plan_only` (40–59) or `halt` (0–39),
- dispatch a `high`/`critical` risk task even at confidence ≥ 60,
- override any `dispatch_allowed:false` decision,
- ship / merge (always — there is **no auto-merge** anywhere in GO-mode).

These mirror the global auto-mode tiers: T1–T3 proceed under the confidence gate;
T4 (force push, hard reset, secrets, irreversible ops) always requires a human.

## Tool budgets

Each dispatched mission carries a `tool_budget` scaled by risk
(see [DISPATCH_PLAYBOOK](DISPATCH_PLAYBOOK.md)): max tool calls, max files, max
subagents. Executors must stay within budget or stop and report.

## Forbidden behavior

- Broad repo wandering (GO selects exactly one task).
- Starting blocked work (`blocked_by` items are excluded).
- Dispatching agents without a mission packet.
- Mutating files below the confidence threshold.
- Bypassing human gates or defining auto-merge.

## Integration points

- **Queue:** beads (`bd ready`) is the live Next Work queue.
- **Confidence:** [CONFIDENCE_GATE_PLAYBOOK](CONFIDENCE_GATE_PLAYBOOK.md).
- **Runtime magnets:** `02_RUNTIME/magnets/{intake,dispatch,decision,closure}_magnet.py`
  implement the same observe→score→decide pattern during live event processing;
  GO-mode is the planning-time entry point that feeds them.
- **Closeout:** `go_mode.summarize()` exposes the last decision to the closeout
  report / `release_readiness` meta-gate via the standard gate contract.
