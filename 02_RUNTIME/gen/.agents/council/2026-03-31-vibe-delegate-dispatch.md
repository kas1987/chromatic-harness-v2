---
id: council-2026-03-31-vibe-delegate-dispatch
type: council
date: 2026-03-31
---

# Vibe Report: delegate router + dispatch UI

**Files Reviewed:** 5
- `src/routes/delegate.ts`
- `src/routes/roles.json`
- `src/index.ts`
- `public/dispatch.html`
- `tests/integration/dispatch-ui.test.ts`

## Complexity Analysis

**Status:** ⚠️ Skipped — TypeScript, no tsc-complexity tool available.

Proxy: `wc -l` sizes — all files within acceptable range (delegate.ts: 599, dispatch.html: 876). No obvious complexity hotspots.

`tsc --noEmit` exits 0 — no type errors.

## Council Verdict: WARN → PASS (after fixes)

| Aspect | Verdict | Notes |
|--------|---------|-------|
| Security | FIXED | Hardcoded dev token replaced with localStorage + URL param |
| Correctness | PASS | Role merging, queue, timeout, fallback all correct |
| Error handling | IMPROVED | Error handler now logs method+path+stack |
| Input validation | IMPROVED | 200k char limit added on delegate prompt |
| Test coverage | WARN | No unit test for role merge precedence or unknown-role 400 |
| Auth | WARN | /ui served without auth (intentional for dev tool, acceptable) |

## CRITICAL Findings — FIXED

- **CRITICAL-1 (FIXED):** Hard-coded dev-placeholder token in dispatch.html replaced with localStorage + URL param bootstrap. No secret in source code. <!-- pragma: allowlist secret -->

## WARN Findings — Remaining

- **WARN-1:** `/ui` static route before `authMiddleware` — intentional (public command center). Accept as-is for dev tool.
- **WARN-2:** No rate limiting on `/api/delegate`. Auth token required, queue capacity (50 jobs) provides natural backpressure. Accept for now, add if public-facing.
- **WARN-3:** Missing unit tests for role merge precedence and unknown-role 400 path. Test gap, not a bug.

## INFORMATIONAL

- `__dirname` resolves to `.` under tsx — `_rolesJsonPath` candidate search handles this correctly (3 paths tried, throws clear error if all fail).
- SQL in DelegationLog uses parameterized queries — no injection risk.
- All DOM updates use `.textContent` — no XSS surface.
- `delegateDb.close()` in graceful shutdown — no resource leak.
- Express error handler now has 4-param signature — previously was 3-param (silent bug treating it as normal middleware).

## Test Results

32/32 Playwright tests pass against live server (`GEN_URL=http://localhost:43123`).

## Recommendation

**SHIP** for internal dev use. Before public/production deploy: add rate limiting and token-in-localStorage UX (prompt user to set token on first load).

## Decision

[x] SHIP — Complexity acceptable, all critical issues fixed, 32/32 tests passing.
