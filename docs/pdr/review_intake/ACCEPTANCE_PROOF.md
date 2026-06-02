# Review Intake — Acceptance Criteria Proof

Epic: `chromatic-harness-v2-tmx5` (re-engineer of the copy-pasted PDR bundle).
PDR: [REVIEW_INTAKE_PDR.md](../../../08_PDRS/PDR_REVIEW_INTAKE_2026-06-01.md) §13.

Every criterion is proven by a fixture-driven test that validates emitted records
against the shipped JSON schemas. Run: `python -m pytest tests/test_review_intake_acceptance.py -q`
and the CI smoke `bash tests/test_review_intake_smoke.sh`.

| # | Acceptance Criterion | Proof (test) | Implementation |
|---|----------------------|--------------|----------------|
| 1 | GitHub review events create valid `review_finding` records | `test_ac1_all_sources_emit_schema_valid_findings` (all 5 sources, schema-validated) | `scripts/review_intake.py` + 5 fixtures |
| 2 | Duplicate comments do not create duplicate queue items | `test_ac2_duplicate_comments_do_not_duplicate_queue_items`, `test_ac2_synchronize_invalidates_stale_queue_items` | dedupe_key + `invalidate_stale_queue_items` (new `pull_request.synchronize` handler, PDR §6) |
| 3 | Queue items include owner, priority, risk, confidence, links, acceptance | `test_ac3_queue_items_complete_and_schema_valid` | `finding_to_queue_item` + `next_work_item.schema.json` |
| 4 | Agent mission packets generated from queue items | `test_ac4_dispatcher_generates_mission_packet_and_dispatch_record` | **new** `scripts/dispatch_review_work.py` (Phase 3 — previously absent) |
| 5 | Branch mutation locks prevent double-patching | `test_ac5_branch_lock_blocks_second_acquire`, `test_ac5_expired_lock_is_reacquirable`, `test_ac5_dispatcher_respects_lock_no_double_patch` | refactored `scripts/lock_pr_branch.py` (importable acquire/release/status), wired into dispatcher |
| 6 | Resolution comments include files changed + validation evidence | `test_ac6_resolution_requires_evidence`, `test_ac6_resolution_with_evidence_logs_schema_valid_record` | hardened `scripts/post_review_resolution.py` (rejects evidence-free Resolved) + new `schemas/review_resolution.schema.json` |
| 7 | Security/architecture/unclear findings are gated, not blindly patched | `test_ac7_security_and_architecture_are_gated`, `test_ac7_gated_items_are_not_dispatched` | `queue_status_for_confidence` gate + dispatcher only selects `ready` |
| 8 | Logs support audit and learning review | `test_ac8_learning_writer_mines_reviewer_patterns` | **new** `scripts/review_learning.py` (reviewer_patterns.jsonl) + JSONL dispatch/resolution logs |

## What the original PRs (5gk1/2irx/maaf) missed

The bundle was unpacked with path tweaks and marked done. The re-engineer added what
was never built or proven:

- **Phase-3 dispatcher** did not exist (`next_work.py` was only a `bd ready` viewer).
- **`pull_request.synchronize`** stale-finding invalidation (PDR §6) was absent.
- **Schema conformance** of emitted records was never tested (4 schemas unused at runtime).
- **Resolution evidence** was not enforced — a Resolved finding could carry no proof.
- **Reviewer-pattern learning** (`reviewer_patterns.jsonl`) had no writer.
- **The GitHub Action** pushed intake artifacts to a protected branch (blocked by the
  pre-push hook) and lacked the `synchronize` trigger; now publishes artifacts and a
  CI smoke job (`.github/workflows/harness-review-intake-check.yml`) exercises all fixtures.
- **Test isolation**: the existing suite wrote to tracked `07_LOGS_AND_AUDIT/review_intake/`
  paths; moved to throwaway temp dirs.
