# Verifier Gate

## Purpose

Prevent worker output from being accepted without review.

## Required Checks

- Objective completed
- Scope respected
- Allowed files only
- Confidence score present
- Risk level present
- Tool budget respected
- Tests or validation completed when applicable
- No human gate bypassed
- Next task provided

## Verifier Output

```json
{
  "task_id": "",
  "verifier": "sonnet | gpt | human",
  "decision": "approve | request_changes | reject | escalate",
  "confidence": 0,
  "issues": [],
  "required_fixes": [],
  "next_task": ""
}
```
