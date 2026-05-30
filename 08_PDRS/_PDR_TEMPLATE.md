# PDR — [Feature Name]

**Status:** draft · **Beads:** `<bd-id>` · **Date:** YYYY-MM-DD

> One-sentence framing: what decision is being made here, and why now.

---

## 1. Problem

*State the concrete, observable gap. What breaks or is missing today? Reference the bead ID or symptom log. One paragraph max.*

---

## 2. Reuse Survey

*What already exists that this can build on or replace?*

| Asset | Location | Role |
|-------|----------|------|
| `existing_module.py` | `02_RUNTIME/...` | extend, not rebuild |
| `config/agent_budget.yaml` | root | add keys, don't duplicate |

*List what is explicitly OUT of scope for reuse (avoid re-litigating later).*

---

## 3. Non-Goals

*Bullet list. Be explicit — ambiguity here costs bead-days.*

- Will NOT add new infra (e.g. no new collector, DB, or sidecar)
- Will NOT change the public API of `<contract file>`
- Will NOT support `<adjacent use case>` in v1

---

## 4. Design

*Describe the approach. Reference file paths. Include the data contract (schema snippets, field names) if this introduces or changes a canonical file. Keep to the decisions that have real tradeoffs — skip the obvious.*

Key contracts / data shapes:

```
# example shape — replace or delete
{ "field": "type", "required": true }
```

---

## 5. Integration / Actuation Edge  ⚠️ MANDATORY

*This is the #1 missed step per the pipeline brief (stage 10). Answer both questions in full:*

**What runtime path calls this?**
> e.g. "PreToolUse hook in `gate.py` reads `routing_policy_overlay.json` on every agent dispatch" — name the exact hook, scheduler, or entrypoint.

**How will we PROVE it is live (not just unit-tested)?**
> e.g. "Trigger a C3 agent dispatch; observe the Magnet log entry within 5 s; `jq .last_actuation quota_state.json` shows a timestamp ≤10 s ago." — this must be a live observation, not a green test run.

*If this section is blank, the spec is not ready to implement.*

---

## 6. Lean Impact  ⚠️ MANDATORY

*Answer every question. Wrong answers here cause boot bloat and always-on polls.*

| Question | Answer |
|----------|--------|
| Boot tax? | e.g. "None — loaded only on PreToolUse; zero import at startup" |
| Always-on vs event-driven? | e.g. "Event-driven Magnet at inflection points — not a poller" |
| On-demand vs always-injected? | e.g. "On-demand; injected only when `billing_axis` is null" |
| Swappable producer? | e.g. "Yes — `quota_state.py` source-abstracts; swap to OTEL without touching consumers" |
| `agent_token_audit.py` baseline | Run before and after; delta must be ≤ X tokens/boot |

*If the answer to any row is "always-on poll", justify it or redesign.*

---

## 7. Decomposition

*Dependency-ordered beads. Each bead is one artifact + its tests.*

| Bead | Artifact | Depends on |
|------|----------|------------|
| **B1** | This spec — the contract | — |
| **B2** ★ | `path/to/first_artifact.py` + unit tests | B1 |
| **B3** | `path/to/second_artifact.py` | B2 |
| **Bn** | Integration wiring / scheduler edit | B2..Bn-1 |

*★ = highest-ROI first step — the one that unblocks everything else with zero infra risk.*

---

## 8. Tests & Hardening

*List the test surface. Hardening is not optional.*

- **Unit tests:** e.g. `pytest tests/test_billing_axis.py` — happy path + edge cases
- **Fail-open:** e.g. "If proxy is down, `quota_state.py` returns `None`; controller falls back to conservative thresholds — never blocks the API path"
- **Security:** e.g. "No secrets in `ledger.jsonl`; `decision_id` is a UUID, not a session token"
- **Staleness guard:** e.g. "5-minute TTL; stale data → conservative defaults, logged WARN"
- **Review gate:** run `review-daemon` before opening PR; security scan on any new network-touching code

---

## 9. Definition of Done

- [ ] All Bn beads closed in `bd`
- [ ] `pytest` green (unit + integration)
- [ ] Integration / Actuation Edge proved live (section 5 checklist passed)
- [ ] `agent_token_audit.py` delta within budget (section 6)
- [ ] `review-daemon` approved
- [ ] PR merged, `bd close <epic-id>`
- [ ] Magnet / telemetry observing in production (stage 11 of pipeline)

*Link to bead: `bd show <epic-id>`*

---

## 10. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| e.g. Header contract changes upstream | Low | Source-abstraction in `quota_state.py`; verify against `/usage` |
| e.g. Controller oscillation | Medium | Deadband + hysteresis + rate limiting |

---

## 11. Rollback

*How do we undo this safely if it goes wrong in production?*

- e.g. "Delete `routing_policy_overlay.json`; `gate.py` falls back to static thresholds on next PreToolUse"
- e.g. "Feature flag `ENABLE_QUOTA_PROXY=false` in `agent_budget.yaml` disables the proxy without code change"
- e.g. "All writes are append-only (`ledger.jsonl`); no destructive migration"
