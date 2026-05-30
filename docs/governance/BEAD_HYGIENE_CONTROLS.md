# Bead Hygiene Controls

This document defines preventive and reactive controls to stop tracker pollution and keep automation reliable.

## Preventive controls

1. Intake duplicate-title prevention:
- Enabled in `02_RUNTIME/intake/auto_intake.py`.
- Before creating a bead from intake, open bead titles are indexed and normalized.
- If a duplicate open title exists, intake entry is marked `skipped` with reason `prevented duplicate open-title`.

2. Canonical telemetry fields:
- Workflow logs include canonical governance fields for downstream detection (`task_id`, `provider`, `model`, `execution_status`, etc.).

3. Queue schema validation:
- Intake queue rejects invalid shape/priority/type/lane at append time.

## Reactive controls

1. Bead hygiene audit:
- Script: `scripts/bead_hygiene_audit.py --write --write-remediation-plan`
- Detects duplicate title groups and malformed IDs.
- Writes artifacts to `.agents/audits/bead_hygiene/`.
- Emits dry-run remediation plan with canonical issue recommendations per duplicate cluster.

2. Daily governance loop integration:
- `scripts/daily_harness_audit.py` executes bead hygiene audit and surfaces findings.
- `scripts/bead_hygiene_remediation_commands.py --write` produces review-only command sets.
- `scripts/bead_hygiene_apply_remediation.py` applies approved remediation targets in controlled batches.

3. Operator remediation policy:
- For duplicate active titles (`OPEN`, `READY`, `IN_PROGRESS`): review and merge/close duplicates by canonical owner issue.
- For malformed IDs: do not mass-edit automatically; route to manual tracker normalization workflow.

## Severity policy

- `P1`: duplicate active title groups exist.
- `P2`: malformed IDs exist but no active duplicate title groups.
- `green`: no active duplicate title groups and no malformed IDs.

## Threshold gate

- Daily strict audit supports `--bead-hygiene-active-duplicate-threshold <N>`.
- When hygiene status is `red`, severity is downgraded to `P2` only when active duplicate count is `<= N`.
- Environment override: `CHROMATIC_BEAD_HYGIENE_ACTIVE_DUPLICATE_THRESHOLD`.

## Commands

- `python scripts/bead_hygiene_audit.py --write`
- `python scripts/bead_hygiene_audit.py --write --write-remediation-plan`
- `python scripts/bead_hygiene_remediation_commands.py --write`
- `python scripts/bead_hygiene_apply_remediation.py --write`
- `python scripts/bead_hygiene_apply_remediation.py --execute --target-id <id> --write`
- `python scripts/daily_harness_audit.py --root . --report --strict`
- `python scripts/daily_harness_audit.py --root . --report --strict --bead-hygiene-active-duplicate-threshold 0`

## Artifacts

- `.agents/audits/bead_hygiene/latest.json`
- `.agents/audits/bead_hygiene/latest.md`
- `.agents/audits/bead_hygiene/latest_remediation_plan.json`
- `.agents/audits/bead_hygiene/latest_remediation_commands.json`
- `.agents/audits/bead_hygiene/latest_remediation_commands.md`
- `.agents/audits/bead_hygiene/latest_remediation_commands.ps1`
- `.agents/audits/bead_hygiene/latest_apply_report.json`

`latest_remediation_commands.json` can contain:
- `duplicate_close`: annotate and close a duplicate into a canonical issue.
- `malformed_review`: annotate a non-canonical ID for manual migration planning.

## Apply safety model

- Default mode for `bead_hygiene_apply_remediation.py` is dry-run.
- Execution requires both `--execute` and one or more `--target-id` values.
- This prevents accidental bulk closure and keeps operator review in the loop.
- `malformed_review` actions do not auto-close issues.
