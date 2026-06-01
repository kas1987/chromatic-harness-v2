# Codex Implementation Handoff: Harness Observability Layer

## Role

You are implementing the first usable observability layer for Chromatic Harness.

## Objective

Install and validate the event logging scripts, schema, and docs in the target repo.

## Inputs

- `00_META/observability/**`
- `scripts/**`
- `.chromatic/**`
- `docs/**`

## Instructions

1. Run Python syntax checks on all scripts.
2. Run `validate_event_log.py` against `ERROR_LOG.jsonl`.
3. Log one bootstrap event.
4. Run the pattern summarizer.
5. Test collision detection with a temporary duplicate writer entry.
6. Report exact files touched and validation results.

## Acceptance Criteria

- All scripts compile.
- Logger appends valid JSONL.
- Validation passes.
- Collision detector exits non-zero when collision exists.
- No secrets are logged.

## Stop Conditions

Stop if destructive actions are required or if secrets are detected.
