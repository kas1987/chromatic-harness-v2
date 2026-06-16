# PDR - Security Dependency Gate Completion

**Status:** in-progress · **Beads:** chromatic-harness-v2-ckqr · **Date:** 2026-06-16 <!-- pragma: allowlist secret -->

Complete dependency vulnerability scanning in local and CI governance flows so security posture is not reported as partially skipped.

---

## 1. Problem

`07_LOGS_AND_AUDIT/security/latest.json` reports secrets status as ok, but dependency checks are `skipped`. This leaves a major supply-chain blind spot and can produce false confidence in release readiness.

---

## 2. Reuse Survey

| Asset | Location | Role |
| ------- | ---------- | ------ |
| security artifact | 07_LOGS_AND_AUDIT/security/latest.json | current status source |
| requirements and pyproject | requirements.txt, pyproject.toml | dependency inventory |
| existing CI workflows | .github/workflows/ | integration point for gating |
| observability health checks | scripts/validate_event_schema.py and related CI checks | precedent for enforcement pattern |

Out of scope for reuse:

- No custom vulnerability database build.

---

## 3. Non-Goals

- Will NOT replace existing secret scanning.
- Will NOT block on low-severity vulnerabilities in phase 1.
- Will NOT require internet access for every local command in strict mode.

---

## 4. Design

1. Add dependency scanner command wrapper with normalized JSON output.
2. Integrate scanner into CI as required check for PRs touching dependency surfaces.
3. Emit summarized dependency findings into security latest artifact.
4. Define severity policy (fail on high/critical by default).

Key contract additions:

{
  "dependencies": {
    "status": "ok|warn|fail",
    "scanner": "[tool]",
    "high_severity": 0,
    "critical_severity": 0,
    "last_scan_utc": "ISO8601"
  }
}

---

## 5. Integration / Actuation Edge  ⚠️ MANDATORY

What runtime path calls this?

- CI workflow for governance/security checks on PR and push events.
- Optional local pre-push hook command for developers.

How will we PROVE it is live (not just unit-tested)?

- Open a dependency-touching PR and observe required dependency scan check in GitHub.
- Confirm `07_LOGS_AND_AUDIT/security/latest.json` includes non-skipped dependency status and timestamp.
- Run local dependency scan command and verify non-zero exit on synthetic high-severity fixture.

---

## 6. Lean Impact  ⚠️ MANDATORY

| Question | Answer |
| ---------- | -------- |
| Boot tax? | None for runtime service path. |
| Always-on vs event-driven? | Event-driven in CI and optional local hook invocation. |
| On-demand vs always-injected? | On-demand scans on dependency changes or explicit run. |
| Swappable producer? | Yes, scanner adapter is abstracted. |
| agent_token_audit.py baseline | No continuous polling introduced. |

---

## 7. Decomposition

| Bead | Artifact | Depends on |
| ------ | ---------- | ------------ |
| B1 | This PDR | - |
| B2 | Scanner adapter script + JSON contract | B1 |
| B3 | CI workflow integration + required check policy | B2 |
| B4 | Security artifact writer integration + docs | B3 |

---

## 8. Tests and Hardening

- Unit tests for scanner output normalization.
- Integration tests for pass/fail severity threshold behavior.
- Fail-open policy for scanner outages in local mode; fail-closed in CI required mode.
- Security hardening: no token/secret leakage in scanner logs.

---

## 9. Definition of Done

- [ ] dependencies status no longer `skipped` in security artifact
- [ ] CI dependency scan check is required on relevant changes
- [ ] high/critical threshold policy documented and enforced
- [ ] local command path documented for developers/operators

---

## 10. Risks

| Risk | Likelihood | Mitigation |
| ------ | ----------- | ------------ |
| Scanner false positives causing merge friction | Medium | Allowlist/exception policy with audit trail |
| Network/tool availability issues | Medium | Cache and fallback modes for local runs |

---

## 11. Rollback

- Revert CI required dependency check to advisory.
- Keep scanner output available as non-blocking artifact until tuned.
