# PDR - Drift Reduction and Root Canon Hardening

**Status:** draft · **Beads:** trsk-drift-canon-hardening · **Date:** 2026-06-16 <!-- pragma: allowlist secret -->

Reduce root and structural drift by enforcing canonical layout checks and guided remediation for safe drift categories.

---

## 1. Problem

`07_LOGS_AND_AUDIT/drift/latest.json` shows low score (`32`) and `trend: worsening`, with unexpected top-level additions and suspicious malformed entries. This indicates root taxonomy drift and weak guardrails around canonical repository structure.

---

## 2. Reuse Survey

| Asset | Location | Role |
|-------|----------|------|
| drift latest artifact | 07_LOGS_AND_AUDIT/drift/latest.json | baseline signal and recommendations |
| canon registry | 00_SOURCE_OF_TRUTH/canon_registry.yaml | expected structure source of truth |
| root artifact hygiene | 07_LOGS_AND_AUDIT/root_artifacts/latest_root_artifact_hygiene.json | complementary hygiene checks |
| pre-session inventory | config/pre_session/inventory.snapshot.json | current inventory snapshot |

Out of scope for reuse:
- No migration to an entirely new repository layout system.

---

## 3. Non-Goals

- Will NOT auto-delete unknown files by default.
- Will NOT change protected path definitions without governance review.
- Will NOT force-move active runtime artifacts without operator signoff.

---

## 4. Design

1. Normalize drift detector output into three categories: intentional additions, suspicious artifacts, malformed entries.
2. Add CI policy gate for malformed and high-risk root drift only.
3. Add safe auto-remediation command generation for known benign drift patterns.
4. Persist decision records for each drift exception accepted by operators.

Key contract additions:

{
  "drift_triage": {
    "intentional": [],
    "suspicious": [],
    "malformed": []
  }
}

---

## 5. Integration / Actuation Edge  ⚠️ MANDATORY

What runtime path calls this?

- `scripts/detect_file_collisions.py`, `scripts/snapshot_git_state.py`, and drift/hygiene scripts feed logs used by guard workflows.
- Drift artifacts are consumed by governance health reporting and session readiness.

How will we PROVE it is live (not just unit-tested)?

- Run drift generation path and verify `07_LOGS_AND_AUDIT/drift/latest.json` includes triage categories.
- Trigger CI workflow on a synthetic malformed root entry and verify required check fails.
- Trigger CI workflow on approved intentional entry and verify pass with recorded exception.

---

## 6. Lean Impact  ⚠️ MANDATORY

| Question | Answer |
|----------|--------|
| Boot tax? | None for runtime; checks run in CI and explicit validation tasks. |
| Always-on vs event-driven? | Event-driven on CI runs and explicit commands. |
| On-demand vs always-injected? | On-demand enforcement in governance pipeline only. |
| Swappable producer? | Yes. Drift producer remains artifact-contract based. |
| agent_token_audit.py baseline | No new always-on component; baseline delta expected near zero. |

---

## 7. Decomposition

| Bead | Artifact | Depends on |
|------|----------|------------|
| B1 | This PDR | - |
| B2 | Drift triage schema and script updates | B1 |
| B3 | CI drift policy gate and allowlist/exception mechanism | B2 |
| B4 | Auto-remediation command generator for safe categories | B3 |

---

## 8. Tests and Hardening

- Unit tests: triage categorization and malformed path detection.
- Integration tests: CI gate pass/fail scenarios.
- Fail-open: if triage cannot classify, default to warn + manual review.
- Security: ensure path normalization prevents injection or traversal tricks.

---

## 9. Definition of Done

- [ ] Drift score at or above 80
- [ ] Drift trend not worsening for at least 7 days
- [ ] Malformed drift entries eliminated from latest artifact
- [ ] CI drift policy gate active and required
- [ ] Exception decisions recorded in audit-friendly format

---

## 10. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Over-blocking valid repository changes | Medium | Exception workflow and explicit allowlist |
| Under-classifying risky entries | Medium | Conservative default classification to suspicious |

---

## 11. Rollback

- Disable strict CI drift gate and return to advisory mode.
- Keep triage code behind feature flag until stable.
