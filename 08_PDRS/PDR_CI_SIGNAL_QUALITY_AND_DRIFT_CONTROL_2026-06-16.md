# PDR - CI Signal Quality and Drift Control

**Status:** draft  
**Track:** ci-signal-drift-control  
**Date:** 2026-06-16

Improve CI signal usability and add controls for toolchain drift to reduce alert
fatigue and avoid silent policy erosion.

---

## 1. Problem

CI currently emits rich data, but reviewers may miss key failures among noisy logs.
In parallel, action/version drift can introduce silent behavior changes and false
confidence.

---

## 2. Design

1. Add summarized CI failure comments for fast triage on PRs.
2. Define a check policy matrix mapping each check to risk class, owner,
   and enforcement level.
3. Add scheduled drift audit to detect action-version and tool-version drift.
4. Add policy compliance check that fails when workflow checks diverge from matrix.

Policy matrix contract:

```yaml
checks:
  security_scan:
    owner: platform-governance
    risk: critical
    enforcement: required
```

---

## 3. Integration / Actuation Edge

- PR feedback path via workflow summary and optional PR comments.
- Governance docs under `docs/` for policy matrix publication.
- Scheduled drift job in `.github/workflows/`.

Live proof:

- PRs show concise failure summary with direct remediation hints.
- Drift audit catches stale pinned versions before incidents.
- Policy mismatch check fails when enforcement and documentation diverge.

---

## 4. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Notification spam on large PRs | Post one consolidated summary per run |
| False positives from drift scanner | allowlist with expiration and owner |
| Policy docs becoming stale | make policy check derive from versioned source of truth |

---

## 5. Definition of Done

- [ ] CI failure summaries enabled for PRs.
- [ ] Check policy matrix committed with owners for all major checks.
- [ ] Scheduled drift audit active with artifact output.
- [ ] Policy-vs-workflow drift gate active in CI.
