# PDR - CI Formatting Debt Burndown

**Status:** draft  
**Track:** ci-format-burndown  
**Date:** 2026-06-16

Reduce repository formatting debt in controlled batches and graduate to
full-repo `ruff format --check .` enforcement.

---

## 1. Problem

Repository-wide Ruff lint now passes, but full formatting gate is still blocked by
legacy formatting drift across many files. This leaves style consistency partially
enforced.

---

## 2. Design

1. Inventory all files failing `ruff format --check .` and bucket by domain.
2. Roll out formatting in bounded batches with dedicated PRs.
3. Protect each batch with targeted regression tests.
4. Promote formatting gate from scoped to full-repo once debt reaches zero.

Batch contract:

```json
{
  "batch": "router-core-01",
  "files": 40,
  "owner": "runtime-platform",
  "required_tests": ["ci-fast", "router-regression"]
}
```

---

## 3. Integration / Actuation Edge

- CI gate in `.github/workflows/ci.yml`.
- Debt-tracking artifact generated per PR batch.
- Optional progress dashboard in `07_LOGS_AND_AUDIT/`.

Live proof:

- Remaining unformatted file count trends to zero.
- No increase in flaky test rate during formatting campaign.
- Final switch to `ruff format --check .` succeeds in CI.

---

## 4. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Large PR conflict storms | Use small, domain-scoped batches |
| Hidden behavior change from edits | Enforce test bundles per batch |
| Team fatigue from style-only reviews | Label as mechanical and auto-approve policy path |

---

## 5. Definition of Done

- [ ] Formatting debt inventory committed.
- [ ] Batch execution plan approved and scheduled.
- [ ] All targeted files formatted and merged.
- [ ] Full-repo format check enabled in CI.
