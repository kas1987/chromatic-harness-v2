# PDR - Unified Guard and Token Governance Recovery

**Status:** draft · **Beads:** trsk-token-gov-recovery · **Date:** 2026-06-16

Recover harness trust posture from red to green by remediating the failing unified guard and token governance strict audit path.

---

## 1. Problem

Current governance posture is red. `07_LOGS_AND_AUDIT/unified_guard/latest.json` reports `ok=false`, and `07_LOGS_AND_AUDIT/token_governance/latest.json` reports `status=red` due to strict daily harness audit failure. This blocks reliable release readiness and degrades confidence in automation gates.

---

## 2. Reuse Survey

| Asset | Location | Role |
|-------|----------|------|
| unified guard artifacts | 07_LOGS_AND_AUDIT/unified_guard/latest.json | primary gate verdict source |
| token governance closed loop | scripts/token_governance_closed_loop.py | closed-loop orchestrator |
| strict daily audit | scripts/daily_harness_audit.py | failing check to remediate |
| session status and observability tasks | scripts/session_status.py, .vscode/tasks.json | operator verification and runbook support |

Out of scope for reuse:
- No new governance framework.
- No rewrite of budget ledger model.

---

## 3. Non-Goals

- Will NOT replace existing guard pipelines.
- Will NOT change public schema contracts for current guard artifacts.
- Will NOT introduce new always-on background services.

---

## 4. Design

1. Build a deterministic remediation runbook around existing guard checks.
2. Add machine-readable failure classification for strict audit failures.
3. Add a prioritized auto-suggestion reducer that maps repeated red statuses to exact remediation commands.
4. Gate completion on consecutive green runs (minimum 3).

Key contract additions:

{
  "remediation_window": {
    "target_green_streak_days": 3,
    "current_green_streak_days": 0,
    "blocking_checks": ["daily_harness_audit_strict"]
  }
}

---

## 5. Integration / Actuation Edge  ⚠️ MANDATORY

What runtime path calls this?

- `scripts/token_governance_closed_loop.py` is called in automation path and writes `07_LOGS_AND_AUDIT/token_governance/latest.json`.
- Unified guard is consumed by session boot and readiness checks.

How will we PROVE it is live (not just unit-tested)?

- Run `python scripts/token_governance_closed_loop.py --enqueue-suggestions --drain-intake`.
- Verify `07_LOGS_AND_AUDIT/token_governance/latest.json` timestamp updates and `status` transitions to green.
- Verify `07_LOGS_AND_AUDIT/unified_guard/latest.json` updates with `ok=true`.
- Capture three consecutive daily runs with green status in artifact history.

---

## 6. Lean Impact  ⚠️ MANDATORY

| Question | Answer |
|----------|--------|
| Boot tax? | Minimal. Uses existing scripts/artifacts; no additional startup poller. |
| Always-on vs event-driven? | Event-driven by explicit run or existing automation entrypoints. |
| On-demand vs always-injected? | On-demand checks and existing session hooks only. |
| Swappable producer? | Yes. Guard producers remain file-contract based. |
| agent_token_audit.py baseline | Required before/after, with no new always-on process introduced. |

---

## 7. Decomposition

| Bead | Artifact | Depends on |
|------|----------|------------|
| B1 | This PDR | - |
| B2 | Failure taxonomy and remediator mapping in token governance closed loop | B1 |
| B3 | Unified guard false-negative and strict-audit red-path fixes | B2 |
| B4 | Green streak tracker and evidence report | B3 |

---

## 8. Tests and Hardening

- Unit: tests for failure classification and remediation map behavior.
- Integration: run strict daily audit and closed loop end to end.
- Fail-open: if remediation mapping fails, emit warning and preserve existing guard output.
- Security: no secrets added to new logs.
- Review gate: review-daemon required before merge.

---

## 9. Definition of Done

- [ ] unified_guard latest artifact reports `ok=true`
- [ ] token governance latest artifact reports `status=green`
- [ ] strict daily audit returns success
- [ ] 3 consecutive daily green runs recorded
- [ ] review-daemon and security checks passed
- [ ] handoff evidence file added under 12_HANDOFFS/sessions/

---

## 10. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Hidden red causes from unrelated subsystems | Medium | Add check-level classification and run isolated repro commands |
| Green flapping | Medium | Require 3-day green streak before closure |

---

## 11. Rollback

- Revert remediation logic changes in closed-loop script.
- Preserve prior artifacts for audit trace.
- Fall back to manual strict-audit workflow using existing scripts.
