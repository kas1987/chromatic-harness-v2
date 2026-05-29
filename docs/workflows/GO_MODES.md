# GO Modes

## Purpose

Define what short commands mean so the harness can continue without vague autonomy.

| Command | Meaning | Mutation |
|---|---|---|
| GO | Pick next safest unblocked task | Allowed if confidence gate passes |
| GO DEEP | Inspect, plan, decompose | No mutation by default |
| GO BUILD | Implement one scoped task | Allowed inside assigned files |
| GO AUDIT | Review and diagnose | No mutation |
| GO VERIFY | Validate previous output | Logs only |
| GO SWARM | Parallel dispatch | Requires approved task graph |
| GO SHIP | Commit → push → PR → merge if confidence gates pass | Uses `workflow_git.py` |

## Default GO Behavior

When user says `GO`:

1. Read project state.
2. Read queue.
3. Select highest priority unblocked task.
4. Build mission packet.
5. Score confidence.
6. Execute only if permitted.
7. Verify and log.
8. Queue next task.

## Self-heal band (50–69)

When confidence is **50–69** and the CMP decision is `replan` or `review` (`plan_only`):

1. **Do not** halt — auto-run the same path as `GO DEEP`.
2. Write `.agents/workflows/active-graph.json` (scout → worker → verifier → scribe).
3. Enqueue scout + build follow-ups on `07_LOGS_AND_AUDIT/intake_queue.jsonl` (`source: workflow`).
4. Return `decision: self_heal` with `next: auto_intake && workflow_go GO`.

Below 50: `halt`. At 70+: normal execute/plan routing. Manual `GO DEEP` still works anytime.
