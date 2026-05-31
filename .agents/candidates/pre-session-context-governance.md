---
name: pre-session-context-governance
source_ids: [2026-05-29-pre-session-context-governance]
source_type: principle
confidence: 0.90
suggested_use: CRG governs the router, not Cursor instruction context
canon_map: knowledge
status: pending
tags: []
---

## Summary

CRG governs the router, not Cursor instruction context

## Evidence

# Learning: CRG governs the router, not Cursor instruction context

## What We Learned

Context Resource Governance (`ContextGate`) budgets harness router resources (~2k tok for coding @ 128k), but Cursor injects enabled MCP JSON schemas separately (~50k+ tok on a typical dev machine). Repo docs and `audit_mcp_context.py` cannot disable MCPs — only Cursor Settings → MCP can.

## Why It Matters

Agents and operators may believe CRG "fixed" pre-session bloat when Cursor context is still dominated by Resend/Playwright/Opsera descriptors. Measure with `session_context_report.py --log` before long sessions.

## Source

Commits `5e7b2b3`, `d1dc82d`, bead `chromatic-harness-v2-e0n` on `feat/k6d-auth-rbac`.

---

# Learning: AUTH_ENABLED must be read at request time

## What We Learned

Module-level `AUTH_ENABLED = os.environ.get(...)` breaks full-suite pytest when `api.main` imports before `test_auth` sets the env var. `is_auth_enabled()` at call time fixes isolation without changing production behavior.

## Why It Matters

Any env-gated FastAPI dependency cached at import will flake in multi-module test order.

## Source

Commit `b4b1d8d`, 150 tests green.

---

# Learning: gate.py CRG used max_tokens=8000 by default

## What We Learned

`RouteConstraints` defaults to 8000 tokens; CRG budget at 25% = 2000 tok, which BLOCKED coding/review/research bundles (~2.1–2.2k). `ROUTER_CONTEXT_MAX_TOKENS=128000` aligns Pi advisories with API tests.

## Why It Matters

False `| CRG BLOCKED` on Agent dispatch erodes trust in harness governance signals.

## Source

`tests/test_gate_context_tokens.py`, `02_RUNTIME/router/gate.py`.
