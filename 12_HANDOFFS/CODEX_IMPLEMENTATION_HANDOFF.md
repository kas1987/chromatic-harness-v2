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

## Observability Compliance (required)

Follow `templates/AGENT_MISSION_PACKET_OBSERVABILITY.md`. In particular:

- **Claim every file before mutating it** (`scripts/claim_files.py`). An
  unclaimed write is a protocol violation — claims are required before mutation.
- **Release all claimed files** when done (`scripts/release_files.py`); a task
  is not complete while any claim is still held.

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
- **All claimed files are released** (no claim left held).

## Stop Conditions

Halt and escalate on any mission-packet stop condition:

- **File-claim collision** (a claim is blocked / another active writer).
- **Dirty-repo ambiguity** (unexplained uncommitted changes; `check_dirty_state.py --strict`).
- **Schema validation failure** (`validate_event_schema.py`).
- **Secret detection** (`scan_for_secrets.py --staged`).
- Any destructive action is required.
