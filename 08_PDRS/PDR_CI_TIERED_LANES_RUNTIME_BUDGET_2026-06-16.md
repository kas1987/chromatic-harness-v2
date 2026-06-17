# PDR - CI Tiered Lanes and Runtime Budget

**Status:** draft  
**Track:** ci-lanes-performance  
**Date:** 2026-06-16

Introduce explicit fast/deep CI lanes with runtime SLOs to reduce PR latency
without sacrificing release confidence.

---

## 1. Problem

Current workflow breadth is comprehensive but expensive. Long feedback loops
increase queue contention and developer wait time, which can encourage bypass
behaviors.

---

## 2. Design

1. Split checks into lane tiers:
   - Fast lane: lint, governance sanity, targeted tests.
   - Deep lane: matrix tests, extended integration, long-running audits.
2. Trigger deep lane on protected branches and risk signals.
3. Define runtime SLOs (median and p95) per lane.
4. Fail lane budget gate when runtime exceeds thresholds for sustained windows.

Runtime budget contract:

```json
{
  "lane": "fast",
  "target_median_minutes": 8,
  "target_p95_minutes": 15,
  "enforcement": "warn_then_required"
}
```

---

## 3. Integration / Actuation Edge

- GitHub Actions workflow decomposition and conditional triggers.
- KPI artifacts under `07_LOGS_AND_AUDIT/` for runtime trend reporting.
- PR status checks that expose lane identity and duration.

Live proof:

- Fast-lane median runtime decreases versus baseline.
- Deep-lane coverage remains stable for high-risk changes.
- Queue wait and rerun rates trend downward.

---

## 4. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Coverage regression from too-light fast lane | Keep deep lane mandatory for protected merges |
| Misrouting risky PRs into fast-only path | Add risk classifier triggers for deep lane |
| KPI gaming | Track both runtime and escape-defect rate |

---

## 5. Definition of Done

- [ ] Lane model implemented and documented.
- [ ] Baseline and post-change runtime metrics published.
- [ ] Fast-lane p95 within target for 2 consecutive weeks.
- [ ] Deep-lane required policy active on protected merges.
