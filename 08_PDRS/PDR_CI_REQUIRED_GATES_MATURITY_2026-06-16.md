# PDR - CI Required Gates Maturity

**Status:** draft  
**Track:** ci-gates-maturity  
**Date:** 2026-06-16

Move high-signal advisory CI checks to required status using a measured,
evidence-first rollout.

---

## 1. Problem

Several checks run with advisory behavior (`continue-on-error`), which reduces
hard-fail noise but can hide regressions when teams ignore artifacts. This creates
security and quality blind-spot risk.

---

## 2. Non-Goals

- Will not make all checks required immediately.
- Will not change branch protection without baseline data.
- Will not block release paths on unstable or low-confidence checks.

---

## 3. Design

1. Build a gate maturity rubric with levels: `advisory`, `candidate_required`,
   `required`.
2. Score each gate by false-positive rate, flake rate, and remediation clarity.
3. Promote only gates that pass thresholds for two weeks.
4. Track promotions and reversions in a versioned policy file.

Policy contract example:

```json
{
  "gate": "security_scan",
  "enforcement": "required",
  "owner": "platform-governance",
  "promotion_window_days": 14,
  "max_flake_pct": 1.0
}
```

---

## 4. Integration / Actuation Edge

- Workflow source: `.github/workflows/ci.yml` and related governance workflows.
- Branch protection source: GitHub required checks configuration.
- Evidence source: CI run logs and `07_LOGS_AND_AUDIT/*` artifacts.

Live proof:

- Required-check list matches declared policy file.
- No critical advisory-only checks remain without documented exception.
- Promotion/reversion events are auditable.

---

## 5. Tests and Hardening

- Unit tests for policy parser and maturity scoring logic.
- Integration smoke test that validates policy -> workflow check name mapping.
- Fallback path: automatic demotion to advisory if flake threshold is exceeded.

---

## 6. Definition of Done

- [ ] Gate maturity matrix committed and reviewed.
- [ ] At least 3 high-value gates promoted to required with low flake rates.
- [ ] Exception process documented for unresolved advisory checks.
- [ ] Weekly gate-health report published.
