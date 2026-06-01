# Agent Mission Packet: Observability Task

## Role

You are acting as a Harness observability implementer or reviewer.

## Objective

Implement or review a bounded change to the Chromatic Harness Observability + Error Intelligence Layer.

## Context

The Harness must log errors, classify failures, detect collisions, preserve evidence, and convert repeated issues into learnings.

## Allowed Files

- `00_META/observability/**`
- `scripts/log_harness_event.py`
- `scripts/redact_secrets.py`
- `scripts/validate_event_log.py`
- `scripts/summarize_error_patterns.py`
- `scripts/detect_file_collisions.py`
- `.chromatic/**`
- `docs/**`

## Forbidden Actions

- Do not delete logs.
- Do not log secrets.
- Do not auto-resolve file collisions.
- Do not edit unrelated project files.
- Do not perform destructive Git operations.

## Output Required

- Summary of change
- Files touched
- Validation performed
- Event IDs created
- Remaining risks
- Next task recommendation

## Acceptance Criteria

- Schema remains valid
- Scripts run without syntax errors
- Redaction is preserved
- Collision behavior halts rather than overwrites
- Learnings require evidence

## Stop Conditions

Stop and report if:

- Required files are missing
- Secret exposure is detected
- A destructive action is needed
- The task expands beyond observability scope
