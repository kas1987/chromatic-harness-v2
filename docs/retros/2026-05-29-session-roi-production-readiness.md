# Session Retrospective — Context ROI, Throughput, Production Readiness

**Date:** 2026-05-29  
**Branch:** `session/chromatic-harness-v2-initial`  
**Last commit (at write):** `1429adf` — fix(roach-pi): wire git submodule and fix Windows init script  
**Merged PR:** [#2 — JWT auth/RBAC + v2 consolidation](https://github.com/kas1987/chromatic-harness-v2/pull/2) (`5e8c8f2`)

> **Beads epic for follow-up:** `chromatic-harness-v2-*` (see `bd show` on epic created 2026-05-29)  
> **Start tomorrow:** `bd ready`

---

## Context usage ROI

Logged snapshots: `.agents/logs/session-context.jsonl`

| When | MCP est. tokens | Cursor session range | Verdict |
|------|-----------------|----------------------|---------|
| Early (~02:07 UTC, harness) | **~51,600** | ~55k–63k | Poor ROI — heavy MCPs dominated pre-session cost |
| Post-hygiene (~04:47 UTC, cursor) | **~5,755** | ~9k–17k | **~9× better** — lean profile, no MCP warnings |

### What paid off

- Measuring context (`scripts/session_context_report.py`, `scripts/audit_mcp_context.py`) instead of trusting CRG alone for Cursor MCP cost
- Repo guardrails: [AGENT_ANTIPATTERNS.md](../AGENT_ANTIPATTERNS.md), lite `/ship` workflows, beads + handoffs instead of chat memory
- “Close loop first” scope ([V2_CONSOLIDATION_BEADS.md](../research/V2_CONSOLIDATION_BEADS.md)) — less re-exploration per turn

### What burned context

- Large PR surface (+19,905 lines) — Copilot could not review (>20k lines)
- Long agent sessions with broad file reads (expected for consolidation)
- Duplicate docker-smoke beads (7×) — process tax, now closed

**ROI summary:** Hygiene + consolidation yielded **high code-per-token** after MCP trim; early-session ROI was poor until heavy MCPs were disabled in Cursor.

---

## Throughput (what we got done)

### Shipped to `session/chromatic-harness-v2-initial`

| Item | Detail |
|------|--------|
| **PR #2 merged** | +19,905 / −261 lines, **241 files** |
| **Follow-up** | `1429adf` — roach-pi gitlink + Windows init script + test fix |
| **Commits (May 28–29)** | ~70+ on integration branch (router, auth, CRG, intake, workflows, console, docs) |

### v2 consolidation epic — complete (P0 → P2)

| Layer | Delivered |
|-------|-----------|
| **P0** | Intake queue schema, bead-intake hook, closure → queue, `auto_intake`, `validate_intake_loop` |
| **P1** | Inbox adapter, task-graph roles, Chromatic MCP server |
| **P2** | Self-heal band, two-log audit, `harvest_rigs`, magnet plugins, test pyramid, WS event store |
| **Plus** | JWT auth/RBAC, dynamic workflow runtime, git confidence pipeline, lite Claude workflows, Agent Lead/magnets, session compact + MCP audit tooling |

### Quality gates (end of session)

| Gate | Result |
|------|--------|
| `pytest tests/` | **226 passed** |
| `validate_intake_loop.py` | OK |
| `check_agent_operations.py` | OK |
| Docker stack | `/health` 200, **12 adapters** |
| roach-pi | submodule **healthy** (`mode: submodule`) |
| `bd ready` / open issues | **empty** (before tomorrow epic) |

---

## Production readiness (honest)

| Subsystem | Readiness | Notes |
|-----------|-----------|--------|
| **API + router (Docker)** | **~75%** | Runs, tests pass; needs prod secrets, monitoring, **GitHub CI green** |
| **Auth / RBAC** | **~65%** | Tested; needs `AUTH_ENABLED`, JWT secrets, deployment hardening |
| **Docs + agent ops** | **~85%** | Strong for a harness repo |
| **Intake → beads loop** | **~60%** | Script-validated; not 24/7 poller/cron + alerting |
| **Workflow GO / git pipeline** | **~55%** | Gates exist; human trust for real ship |
| **Magnets / Agent Lead** | **~50%** | Partial per [gaps landscape](../research/CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md) |
| **Frontend console** | **~45%** | Next 15 dev in compose; no prod build path |
| **roach-pi runtime** | **~40%** | Submodule healthy; integration path immature |
| **P3 maturity** | **~25%** | Full MCP mesh, L0–L5 autonomy, playbook evolution — deferred |

**Overall:** Strong **integration / dev harness**; not yet **unattended production platform**.

### Blockers before “production”

1. **GitHub Actions** — PR #2 had no reported checks; confirm Actions enabled + green on default branch
2. **Operational loop** — schedule `poll_inbox` / `auto_intake`, monitor `07_LOGS_AND_AUDIT/intake_queue.jsonl`
3. **Deploy path** — console prod build (not `npm run dev` in compose)
4. **Security** — auth secrets, untrusted surfaces per antipatterns doc
5. **Scope discipline** — no unattended `/crank` or council chains

---

## Recommended next session (tomorrow)

```bash
git checkout session/chromatic-harness-v2-initial && git pull
bd ready
python scripts/session_context_report.py --log --invoked-by cursor
python scripts/audit_mcp_context.py --profile harness_dev
python scripts/validate_intake_loop.py
```

Priority order (also filed as beads):

1. **CI green** on `session/chromatic-harness-v2-initial`
2. **Ops runbook** — compose, intake validation, auto_intake, auth env
3. **Console prod build** in deployment
4. **Intake poller** scheduling / monitoring
5. **P3** — autonomy levels, playbook evolution, MCP ecosystem (when loop is ops-stable)

---

## References

- [V2_CONSOLIDATION_BEADS.md](../research/V2_CONSOLIDATION_BEADS.md)
- [CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md](../research/CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md)
- [AGENT_ANTIPATTERNS.md](../AGENT_ANTIPATTERNS.md)
- [CURSOR_CONTEXT_HYGIENE.md](../CURSOR_CONTEXT_HYGIENE.md)
