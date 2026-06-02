# Auditor Review Handoff: Harness Observability Layer

## Role

You are auditing the observability package for operational control, evidence quality, and safety.

## Objective

Determine whether this package is sufficient to prevent silent failures, repeated debugging, collision loss, and untracked incidents.

## Checks

- Required event fields exist.
- Severity model is clear.
- Collision path halts mutation.
- Secret exposure is handled as critical.
- Learnings require evidence.
- Scripts can validate logs.
- Agent usage rules are bounded.

## Output Required

| Check | Pass/Fail | Evidence | Fix Required |
|---|---|---|---|

## Stop Conditions

Stop if the package encourages destructive automation or unredacted logging.
