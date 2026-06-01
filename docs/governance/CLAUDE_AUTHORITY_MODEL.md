# Claude Authority Model

## Summary

Claude is an interface. The harness is the control plane.

## Authority Ladder

```text
L0 Human Intent
L1 GitHub Issues / bd Queue
L2 Harness Router / Orchestrator
L3 Confidence Gate
L4 Lease / Collision Gate
L5 Verifier Gate
L6 Tests / CI Governance
L7 Release Readiness
L8 Human Approval for irreversible actions
```

Claude commands may only operate as adapters into this ladder.

## Authority Boundaries

| Decision | Authority |
|---|---|
| What work exists | GitHub issues / bd queue |
| What work starts next | Queue + orchestrator |
| Whether mutation is allowed | Confidence + lease gates |
| Whether T3+ work is promotable | Verifier gate |
| Whether code can ship | `workflow_git.py` + tests + CI |
| Whether release is allowed | release readiness |
| Whether emergency override is allowed | Human |

## Claude Role

Claude may:

- translate human intent into a harness command;
- show status;
- summarize reports;
- explain why the harness blocked;
- prepare issue/PDR/queue artifacts;
- propose next safe action.

Claude may not:

- override authority gates;
- claim work without queue/lease;
- ship without verifier/test/CI path;
- mutate state because a conversation feels clear.
