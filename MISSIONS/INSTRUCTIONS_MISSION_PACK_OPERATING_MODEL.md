# Instructions: Mission Pack Operating Model

## 1. Command Rules

### Human Commands

| Command | Meaning |
|---|---|
| `GO` | Continue from the next approved item in the handoff queue. |
| `GO PLAN` | Create or improve a Mission Pack; do not implement. |
| `GO BUILD` | Implement an approved Mission Pack. |
| `GO AUDIT` | Review a completed mission and produce findings. |
| `GO CLOSE` | Close a mission, update logs, and queue next task. |
| `ESCALATE` | Stop implementation and prepare a human-gate request. |

## 2. Mission Intake

Before planning or implementation, capture:

- Objective.
- Requested outcome.
- Known files or systems.
- Risk guess.
- Urgency.
- Whether this is reversible.
- Whether user approval is required.

## 3. Classification Procedure

1. Assume M1 only if the task is simple, small, and low risk.
2. Escalate to M2 if there are multiple steps, dependencies, tests, or moderate uncertainty.
3. Escalate to M3 if the task touches multiple systems, architecture, security posture, performance, database shape, or agent behavior.
4. Escalate to M4 if the task is irreversible, production-facing, secret-sensitive, data-destructive, or requires full sign-off.

## 4. Review Procedure

The reviewer must check:

- Is the mission level correct?
- Is the objective measurable?
- Is the scope tight enough?
- Are forbidden areas listed?
- Are risks and rollback appropriate for the level?
- Is validation strong enough?
- Is the agent/tool budget reasonable?
- Is approval required?

## 5. Implementation Procedure

Builder agents must:

1. Read only the packet and directly relevant files.
2. Confirm confidence score.
3. Stop if confidence is below the threshold.
4. Modify only allowed files.
5. Respect tool budget.
6. Run required validation.
7. Return evidence.
8. Update or request update to logs.

## 6. Validation Procedure

Validation must be proportional:

| Level | Minimum Validation |
|---|---|
| M1 | Self-review and basic acceptance check. |
| M2 | Targeted test, diff review, and acceptance criteria verification. |
| M3 | Comprehensive test strategy, integration review, rollback check. |
| M4 | Exhaustive validation, formal sign-off, rollback proof, audit trail. |

## 7. Closeout Procedure

A mission cannot close until it includes:

- Outcome.
- Files changed.
- Tests or checks performed.
- Acceptance criteria status.
- Risks introduced or retired.
- Decisions made.
- Lessons learned.
- Next recommended task.

