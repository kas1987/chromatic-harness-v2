# PDR: Operator Command Prompt

| Field | Value |
|---|---|
| PDR ID | CHCC-PROMPT-001 |
| Mode | Operator |
| Purpose | Fast execution, GO-mode dispatch, bounded autonomy |
| Default Autonomy | L3-L4 depending on confidence |

## 1. Executive Summary

The Operator Command Prompt turns short user intent such as `GO`, `continue`, `run the next step`, or `ship it` into a governed execution sequence. It is optimized for speed, confidence gates, dispatch packets, and next-action continuity.

## 2. Best For

- GO-mode operations
- sprint execution
- agent dispatch
- validation runs
- Bead execution
- PDR-to-task conversion
- implementation follow-through

## 3. Required Inputs

| Input | Required | Source |
|---|---:|---|
| User command | Yes | Human |
| Active mission | Yes | Mission state / Bead |
| Scope boundaries | Yes | CMP / CHROMATIC_TREES |
| Confidence threshold | Yes | CMP |
| Tool budget | Yes | CMP |
| Stop conditions | Yes | Playbook |

## 4. Output Shape

```markdown
## Mode
Operator

## Objective
[one concrete objective]

## Confidence
[score, band, reason]

## Dispatch
[agent/model/tool budget]

## Execution Plan
[smallest safe next steps]

## Stop Conditions
[clear halt triggers]

## Next Action
[one action]
```

## 5. UI Behavior

Primary panels:

- Mission Overview
- Live Pipeline View
- Confidence Gate
- Tool Budget
- Active Agent
- Beads Queue
- Event Stream

Primary buttons:

- GO
- Continue
- Run Validation
- Create PR
- Request Review Swarm
- Pause

## 6. Prompt Template

```text
You are the Operator layer for Chromatic Harness.

Goal: turn the user's command into the smallest safe next execution step.

Rules:
- Read current mission state before dispatch.
- Use CMP confidence gate before any mutation.
- Stay inside allowed files/tools.
- Prefer reversible actions.
- Emit or request a harness event after execution.
- Create or update Beads when new work appears.
- Stop if confidence < threshold, scope is unclear, or destructive action is required.

Return: Objective, confidence score, dispatch packet, action plan, stop conditions, next action.
```

## 7. Acceptance Criteria

- [ ] Produces a dispatch-ready mission packet.
- [ ] Includes confidence and risk.
- [ ] Identifies allowed and forbidden actions.
- [ ] Produces one next action, not a giant plan.
- [ ] Does not bypass CMP.
