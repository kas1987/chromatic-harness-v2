# PDR - CI/CD SWOT Remediation Portfolio

**Status:** draft  
**Track:** ci-cd-sprint-remediation  
**Date:** 2026-06-16

Coordinate and sequence all CI/CD remediation work identified in [08_PDRS/SWOT_CI_CD_2026-06-16.md](08_PDRS/SWOT_CI_CD_2026-06-16.md).

---

## 1. Problem

SWOT analysis identified gaps in enforcement consistency, runtime efficiency,
quality signal clarity, and operational governance in CI/CD. Immediate fixes were
landed (repo-wide Ruff check and changed-markdown lint), but larger structural
remediation requires coordinated execution.

---

## 2. Portfolio Scope

| PDR | Focus | SWOT Areas Covered |
| --- | --- | --- |
| `PDR_CI_REQUIRED_GATES_MATURITY_2026-06-16.md` | advisory-to-required conversion model | weaknesses 4, threats 1/3 |
| `PDR_CI_TIERED_LANES_RUNTIME_BUDGET_2026-06-16.md` | fast/deep lanes + runtime budget SLOs | weaknesses 3, opportunities 3, threats 4 |
| `PDR_CI_FORMAT_DEBT_BURNDOWN_2026-06-16.md` | staged formatter debt reduction | weaknesses 5, opportunities 5 |
| `PDR_CI_SIGNAL_QUALITY_AND_DRIFT_CONTROL_2026-06-16.md` | evidence UX + toolchain drift controls | opportunities 2/4, threats 1/2 |

---

## 3. Sequencing

1. Start with `required_gates_maturity` to harden correctness and compliance.
2. In parallel, run `tiered_lanes_runtime_budget` to improve feedback time.
3. Execute `format_debt_burndown` in staged waves to avoid destabilizing PRs.
4. Land `signal_quality_and_drift_control` to reduce fatigue and long-term drift.

---

## 4. Integration / Actuation Edge

Runtime paths affected:

- GitHub Actions workflows under `.github/workflows/`
- Documentation governance under `08_PDRS/` and `docs/`
- Release readiness and review quality gates in existing harness scripts

Live proof requirements:

- Required-check set in GitHub branch protection reflects approved matrix.
- PRs show fast-lane checks under target runtime and deep-lane coverage.
- Formatter debt KPI trends down each week with no spike in flaky checks.
- Drift-control jobs catch stale action versions and policy mismatches.

---

## 5. Definition of Done

- [ ] All four implementation PDRs approved and linked in a single execution board.
- [ ] Owners, milestones, and acceptance metrics assigned per PDR.
- [ ] CI/CD SWOT weaknesses have a tracked remediation path with evidence links.
- [ ] Portfolio closeout report added under `12_HANDOFFS/`.
