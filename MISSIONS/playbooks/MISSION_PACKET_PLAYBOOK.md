# Mission Packet Playbook

## Purpose

This playbook defines how the Harness creates, scores, reviews, dispatches, validates, and closes Mission Packs.

## Operating Loop

```text
Observe → Classify → Score → Decide → Packetize → Review → Execute → Validate → Record → Queue Next
```

## Dispatch Rule

No agent receives work without a Mission Packet containing:

- Task ID.
- Objective.
- Allowed files.
- Forbidden files.
- Allowed tools.
- Tool budget.
- Risk level.
- Confidence score.
- Definition of done.
- Stop conditions.
- Required output.

## Stop Conditions

Stop immediately when:

- Confidence drops below threshold.
- Required context is missing.
- Scope expands beyond packet.
- A forbidden file must be changed.
- Validation cannot be run.
- Human approval is required.
- Secret, production, data, or security risk appears.

## Output Format

```md
## Mission Result

- Mission ID:
- Level:
- Status:
- Summary:
- Files Changed:
- Tests / Validation:
- Acceptance Criteria Result:
- Risks:
- Follow-Up:
- Next Recommended Task:
```
