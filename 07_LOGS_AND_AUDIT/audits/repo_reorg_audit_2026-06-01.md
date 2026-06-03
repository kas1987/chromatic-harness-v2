# Repo Re-org Audit — Review Intake PDR vs Harness Layout

**Date:** 2026-06-03  
**Auditor:** Cursor agent (canon-sync plan)  
**Verdict:** **No full repo re-org.** Path remapping only; restore `CHROMATIC_TREES.md` and align PDR/protocol docs.

## Executive summary

| Question | Answer |
|----------|--------|
| Re-unpack `chromatic_review_intake_pdr.zip`? | **No** — harness already implements review intake under `07_LOGS_AND_AUDIT/review_intake/` |
| Adopt zip layout (`00_PLANNING/`, `02_LOGS/`, `03_PLAYBOOKS/`)? | **No** — creates orphaned trees |
| Full numbered-tree re-org? | **No** |
| Required follow-up | Canon sync: restore `CHROMATIC_TREES.md`, patch PDR §11, fix bead protocol queue paths, remove legacy `10_RUNTIME` dirs |

## Path mapping (zip scaffold → harness)

| PDR zip | Harness (canonical) |
|---------|---------------------|
| `00_PLANNING/review-findings.jsonl` | `07_LOGS_AND_AUDIT/review_intake/findings.jsonl` |
| `00_PLANNING/next-work.queue.json` | `07_LOGS_AND_AUDIT/review_intake/queue.json` |
| `00_PLANNING/review-intake.state.json` | `07_LOGS_AND_AUDIT/review_intake/state.json` |
| `02_LOGS/*-log.jsonl` | `07_LOGS_AND_AUDIT/review_intake/dispatch_log.jsonl`, `resolution_log.jsonl`, `reviewer_patterns.jsonl` |
| `03_PLAYBOOKS/REVIEW_*.md` | `04_PLAYBOOKS/REVIEW_*` + `PR_COLLISION_CONTROL_PLAYBOOK.md` |
| `05_DOCS/REVIEW_INTAKE_PDR.md` | `08_PDRS/PDR_REVIEW_INTAKE_2026-06-01.md`, `docs/pdr/review_intake/` |

Code default: `scripts/review_intake.py` → `DEFAULT_BASE = "07_LOGS_AND_AUDIT/review_intake"`.

## Verification commands (2026-06-03)

| Command | Result |
|---------|--------|
| `python scripts/rudalo_migration_audit.py` | COMPLETE; legacy `10_RUNTIME`, `02_RUNTIME/10_RUNTIME` warn (logs only) |
| `python scripts/root_artifact_hygiene.py` | DRY_RUN planned=1 (`.coverage` delete) |
| `python scripts/validate_schema_registry.py` | All 15 schemas PASSED |
| `python -m pytest tests/test_review_intake_acceptance.py -q` | 15 passed |
| `python scripts/daily_harness_audit.py --root . --report` | Completed (lock wait p95 noted in rollup) |

## Structural findings

1. **P0** — `CHROMATIC_TREES.md` deleted in `15a8ba89` (PR #233); references remained in README, visual control plane, registry. **Action:** restored from `d3aec011` and reconciled in canon-sync PR.
2. **P1** — `08_PDRS/PDR_REVIEW_INTAKE_2026-06-01.md` §11 listed zip paths. **Action:** patched to harness paths.
3. **P1** — `BEAD_EPIC_AUTHORING_PROTOCOL.md` referenced non-existent `00_PLANNING/`. **Action:** pointed to `07_LOGS_AND_AUDIT/review_intake/queue.json`.
4. **P2** — Legacy `10_RUNTIME/` dirs exist (logs only). **Action:** removed per Rudalo audit.
5. **P2** — `docs/` vs `02_DOCS/` dual tree; `02_DOCS` deprecated in `CHROMATIC_TREES` §4 (no mass merge this PR).
6. **Closed** — Review intake implementation proven (`docs/pdr/review_intake/ACCEPTANCE_PROOF.md`, epic `chromatic-harness-v2-tmx5`).

## Drift scan (`CHROMATIC_TREES` / `00_PLANNING`)

Active doc references to fix in canon-sync: `08_PDRS/PDR_REVIEW_INTAKE_2026-06-01.md`, `docs/playbooks/BEAD_EPIC_AUTHORING_PROTOCOL.md`, visual control plane chain (now resolve to restored root file). Historical retros may still mention zip paths for archaeology.

## Decision log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-03 | Canon sync only (user scope) | Implementation complete; re-org risk >> benefit |
| 2026-06-03 | Restore `CHROMATIC_TREES.md` at repo root | Single structural SoT per harness conventions |
