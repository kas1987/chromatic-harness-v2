# Post-Mortem Council — Context Hygiene + Auth (2026-05-29)

**Scope:** `b4b1d8d`, `5e7b2b3`, `d1dc82d` on `feat/k6d-auth-rbac`  
**Tests:** 155 passed  
**Bead:** `chromatic-harness-v2-e0n` closed

## Verdict: PASS (with operator WARN)

---

### plan-compliance

| Planned | Delivered |
|---------|-----------|
| Fix auth test isolation | `is_auth_enabled()` — done |
| MCP hygiene for Cursor/Claude | profiles, audit, hygiene doc, Cursor rule — done |
| CRG false BLOCKED on Pi | `ROUTER_CONTEXT_MAX_TOKENS` — done |
| Unified logging Cursor/Claude/Harness | `session_context_report.py` + JSONL — done |
| User disables MCPs in UI | **Not automatable** — documented, still ~51k on disk |

**Missing from code (by design):** Cursor MCP toggle API — operator action required.

---

### tech-debt

| Item | Severity |
|------|----------|
| MCP descriptors remain on disk when disabled in UI | low |
| `~/AGENTS.md` may duplicate workspace `AGENTS.md` (~1.4k tok) | low |
| `bd` not on PATH in some hook shells | medium |
| Session log shows MCP upper bound, not actual Cursor toggle state | medium |
| `02_RUNTIME/api/10_RUNTIME/` accidental logs untracked | low — delete locally |

---

### learnings

- Three-layer model (instruction / invoked / CRG) must be taught to every agent.
- `session-context.jsonl` gives a flywheel metric for context cost over time.
- Resend MCP alone ~31k tok — disable-first wins more than router policy tweaks.

---

## Four-surface closure

| Surface | Status |
|---------|--------|
| Code | PASS — scripts, gate, auth, tests |
| Documentation | PASS — AGENT_OPERATIONS, CURSOR_CONTEXT_HYGIENE, CI |
| Examples | PASS — audit/report CLI usage in docs |
| Proof | PASS — 155 pytest, pre-push E2E green, log line captured |
