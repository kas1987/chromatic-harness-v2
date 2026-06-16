# PDR - Telemetry Coverage and Token Taxonomy Quality

**Status:** draft · **Beads:** trsk-telemetry-coverage-taxonomy · **Date:** 2026-06-16 <!-- pragma: allowlist secret -->

Improve token telemetry quality and routing confidence by reducing unknown token event classifications and restoring confidence/cost/latency coverage checks to green.

---

## 1. Problem

Token governance artifacts show high unknown event share (`unknown_pct ~ 70.91`) and harness health fails confidence/cost/latency coverage checks. This weakens budget forecasting, model-routing policy quality, and governance explainability.

---

## 2. Reuse Survey

| Asset | Location | Role |
|-------|----------|------|
| token governance artifacts | 07_LOGS_AND_AUDIT/token_governance/latest.json | source of unknown rate and checks |
| telemetry ledger | 07_LOGS_AND_AUDIT/budget/ledger.jsonl | raw spend/event signal |
| command matrix | 07_LOGS_AND_AUDIT/command_matrix/latest.json | command-to-intent context |
| governance routing docs | docs/routing/multi-router-matrix.yaml | policy mapping reference |

Out of scope for reuse:
- No replacement of budget ledger format.
- No external telemetry platform migration in v1.

---

## 3. Non-Goals

- Will NOT alter billing totals retroactively.
- Will NOT force strict rejection of unknown events at emit time in first rollout.
- Will NOT add heavy always-on enrichment services.

---

## 4. Design

1. Define canonical taxonomy map for provider/model/task/confidence/cost/latency event fields.
2. Add ingestion-time normalization and fallback labels for currently unknown records.
3. Add backfill tool for historical ledger classification where deterministic.
4. Add quality gate thresholds to fail when unknown ratio exceeds policy limit.

Key contract additions:

{
  "telemetry_quality": {
    "unknown_pct_threshold": 20.0,
    "unknown_pct_current": 70.91,
    "coverage_confidence": 0.0,
    "coverage_cost": 0.0,
    "coverage_latency": 0.0
  }
}

---

## 5. Integration / Actuation Edge  ⚠️ MANDATORY

What runtime path calls this?

- Token governance closed-loop workflow ingests telemetry and writes quality metrics to `07_LOGS_AND_AUDIT/token_governance/latest.json`.
- Harness health checks consume those metrics for readiness scoring.

How will we PROVE it is live (not just unit-tested)?

- Run closed-loop workflow and verify unknown percentage drops in latest artifact.
- Run harness health and verify confidence/cost/latency coverage checks transition from fail/warn to pass.
- Validate sample command/session produces classified token telemetry end to end.

---

## 6. Lean Impact  ⚠️ MANDATORY

| Question | Answer |
|----------|--------|
| Boot tax? | Minimal; normalization at existing ingestion points. |
| Always-on vs event-driven? | Event-driven via telemetry ingest and scheduled governance checks. |
| On-demand vs always-injected? | Always-injected only in existing ingestion path; no new service loop. |
| Swappable producer? | Yes. Taxonomy map is configuration-backed. |
| agent_token_audit.py baseline | Required; no additional background pollers permitted. |

---

## 7. Decomposition

| Bead | Artifact | Depends on |
|------|----------|------------|
| B1 | This PDR | - |
| B2 | Taxonomy map and normalization functions | B1 |
| B3 | Historical backfill tool and dry-run report | B2 |
| B4 | Quality thresholds and health gate wiring | B3 |

---

## 8. Tests and Hardening

- Unit tests for mapping, normalization, and fallback logic.
- Integration test from command event to governance artifact coverage fields.
- Fail-open: unknown events preserved with explicit fallback label.
- Security: no PII/secrets included in enriched telemetry fields.

---

## 9. Definition of Done

- [ ] Unknown telemetry percentage below 20%
- [ ] Coverage confidence/cost/latency checks are green in harness health
- [ ] Taxonomy map versioned and documented
- [ ] Backfill runbook and report committed

---

## 10. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Misclassification of edge cases | Medium | Conservative fallback labels and audit sampling |
| Policy drift across tools | Medium | Single shared taxonomy config with schema validation |

---

## 11. Rollback

- Disable strict quality threshold enforcement.
- Keep normalization in advisory mode while preserving raw event values.
# PDR - Telemetry Coverage and Token Taxonomy Reliability

**Status:** draft · **Beads:** trsk-telemetry-coverage-reliability · **Date:** 2026-06-16 <!-- pragma: allowlist secret -->

Increase token telemetry reliability by reducing unknown event classification and improving confidence/cost/latency coverage quality.

---

## 1. Problem

Token governance artifacts indicate high unknown classification (`unknown_pct` around `70.91` in `07_LOGS_AND_AUDIT/token_governance/latest.json`). Harness health also reports weak confidence/cost/latency coverage. This reduces the quality of routing and budget decisions.

---

## 2. Reuse Survey

| Asset | Location | Role |
|-------|----------|------|
| token governance artifact | 07_LOGS_AND_AUDIT/token_governance/latest.json | source of unknown classification signal |
| budget ledger | 07_LOGS_AND_AUDIT/budget/ledger.jsonl | event-level telemetry corpus |
| telemetry report | 05_REPORTS/telemetry.jsonl | auxiliary signal path |
| command matrix | 07_LOGS_AND_AUDIT/command_matrix/latest.json | mapping candidate source |

Out of scope for reuse:
- No replacement of existing budget ledger storage format.

---

## 3. Non-Goals

- Will NOT change historic ledger records destructively.
- Will NOT block runtime command execution for unknown taxonomy in v1.
- Will NOT introduce paid external telemetry providers.

---

## 4. Design

1. Define and enforce a canonical token event taxonomy at emit points.
2. Add mapping backfill logic to classify existing unknown categories where safe.
3. Add explicit unknown bucket diagnostics by agent, command family, and workflow.
4. Add SLO targets and fail thresholds for unknown percentage.

Key contract additions:

{
  "telemetry_quality": {
    "unknown_pct": 0.0,
    "unknown_by_source": {},
    "target_unknown_pct": 20.0
  }
}

---

## 5. Integration / Actuation Edge  ⚠️ MANDATORY

What runtime path calls this?

- Telemetry writers in harness command and workflow paths append to budget and telemetry artifacts.
- Token governance closed loop consumes these artifacts to evaluate health.

How will we PROVE it is live (not just unit-tested)?

- Trigger representative agent commands across at least three workflows.
- Verify new records in `07_LOGS_AND_AUDIT/budget/ledger.jsonl` include canonical taxonomy fields.
- Verify `07_LOGS_AND_AUDIT/token_governance/latest.json` shows reduced unknown percentage.
- Verify health check no longer fails confidence/cost/latency coverage checks.

---

## 6. Lean Impact  ⚠️ MANDATORY

| Question | Answer |
|----------|--------|
| Boot tax? | None expected; taxonomy checks occur at emit time only. |
| Always-on vs event-driven? | Event-driven per command/event emission. |
| On-demand vs always-injected? | Always at emit path, but no separate background poller. |
| Swappable producer? | Yes, taxonomy map can be versioned and swapped without ledger schema rewrite. |
| agent_token_audit.py baseline | Must show no new scheduler/poller introduced. |

---

## 7. Decomposition

| Bead | Artifact | Depends on |
|------|----------|------------|
| B1 | This PDR | - |
| B2 | Canonical token event taxonomy contract | B1 |
| B3 | Emit-path mapper upgrades and diagnostics | B2 |
| B4 | Backfill utility and quality dashboard extension | B3 |

---

## 8. Tests and Hardening

- Unit tests: taxonomy mapping and fallback behavior.
- Integration tests: end-to-end command emission to ledger classification.
- Fail-open: unknowns remain allowed but logged with explicit diagnostics.
- Security: ensure no sensitive payloads are logged in taxonomy fields.

---

## 9. Definition of Done

- [ ] unknown token event percentage under 20%
- [ ] confidence/cost/latency coverage checks green
- [ ] unknown-by-source diagnostics visible in artifact output
- [ ] no new always-on telemetry poller introduced

---

## 10. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Overfitting taxonomy to current workflows | Medium | version taxonomy and keep unknown fallback |
| Mapping ambiguity for legacy events | High | preserve unknown label when confidence is low |

---

## 11. Rollback

- Revert mapper changes and continue with legacy classification path.
- Keep diagnostics in advisory-only mode.
