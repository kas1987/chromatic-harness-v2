# Phase 1 Security Status

Date: 2026-08-01
Scope: Security hard-stop verification and remediation only
Base baseline: 12_HANDOFFS/baseline/BASELINE_CLAIM_LEDGER_2026-08-01.md

## Outcome
- Security hard-stop checks are remediated and verified.
- The Phase 1 closeout proof rerun passed: the complete security pytest bundle, both security scanners, and `git diff --check` are green.
- No remaining hard-stop is attributable to the Phase 1 security surface.
- The only non-Phase-1 edit used during closeout was removal of two trailing spaces from `docs/PRE_SESSION_AND_TOOLS.md:3` so `git diff --check` could run clean; that docs file is outside the Phase 1 checkpoint commit.

## Security changes made
- `02_RUNTIME/api/auth.py`
  - Authentication now defaults to enabled unless explicitly disabled.
  - Predictable fallback secret removed; production now requires `AUTH_SECRET_KEY` to be configured.
  - Role helpers now depend on `require_current_user`, making role-gated dependencies explicit and non-optional.
- `02_RUNTIME/api/main.py`
  - Sensitive API routes now declare explicit `require_executor` or `require_reviewer` dependencies.
  - Agent promotion now requires reviewer-or-higher access.
- `09_DEPLOYMENT/claude-relay/relay.py`
  - Relay now defaults to localhost binding, requires a bearer token outside dev mode, enforces a request-body size cap, and restricts accepted models to an allowlist.
- `.github/workflows/ci.yml`
  - Added top-level least-privilege `permissions`.
  - Added `persist-credentials: false` to checkout steps.
- `tests/test_api.py`
  - Added reviewer-enforcement regression coverage for agent promotion.
- `tests/test_relay_security.py`
  - Added coverage for relay auth enforcement, localhost-only operation, model allowlisting, and request-body limits without shelling out to the real CLI.
- `tests/test_security_scan.py`
  - Kept secret-scan behavior intact while removing tracked secret-shaped literals from file text.
- `tests/02_RUNTIME/router/test_privacy.py`
  - Kept privacy detection behavior intact while removing tracked secret-shaped literals from file text.
- `requirements.txt`
  - Replaced `python-jose` with `PyJWT` to remove the vulnerable `ecdsa` dependency chain.
- `tests/02_RUNTIME/api/test_api_endpoints.py`
  - Removed the old jose-specific shim, made the suite explicitly auth-disabled, and fixed its event-loop fixture so it can run against the real JWT stack.

## Verification run
1. Focused security suite after first remediation:
   - `python -m pytest tests/test_api.py tests/test_auth.py tests/test_relay_security.py -q`
   - Result: 26 passed
2. Focused security plus secret-pattern suite after final remediation:
   - `python -m pytest tests/test_api.py tests/test_auth.py tests/test_relay_security.py tests/test_security_scan.py tests/02_RUNTIME/router/test_privacy.py -q`
   - Result: 62 passed
3. Broader security proof set:
  - `python -m pytest tests/test_api.py tests/test_auth.py tests/test_relay_security.py tests/test_security_scan.py tests/test_service_auth_audit.py tests/02_RUNTIME/router/test_privacy.py -q`
  - Result: 70 passed
  - Note: coverage emitted pre-existing `.coverage` parsing warnings on Windows; test outcomes still passed.
4. Auth-stack replacement proof set:
  - `python -m pytest tests/test_api.py tests/test_auth.py tests/test_relay_security.py tests/test_security_scan.py tests/test_service_auth_audit.py tests/02_RUNTIME/router/test_privacy.py tests/02_RUNTIME/api/test_api_endpoints.py -q`
  - Result: 139 passed
3. Diagnostics on touched files:
   - `get_errors` for all touched Phase 1 files
   - Result: no errors found
4. Read-only benchmark rerun:
   - `python 12_HANDOFFS/baseline/run_benchmark.phase0.py --repo c:/Users/kas41/chromatic-harness-v2`
   - Persisted result: `12_HANDOFFS/baseline/benchmark_phase1_security.json`
   - Score: 88.83
   - Security domain: 38.0 / 38.0
   - Remaining hard-stop: `git diff --check` failure in `docs/PRE_SESSION_AND_TOOLS.md`
5. Runtime security scanners:
  - `python scripts/service_auth_audit.py --json --save`
  - Result: overall risk LOW, 0 critical findings, artifact at `07_LOGS_AND_AUDIT/security/service_auth_latest.json`
  - `python scripts/security_scan.py --json`
  - Result: secrets clean, dependency scan clean, 0 high-severity findings
  - Artifact: `07_LOGS_AND_AUDIT/security/latest.json`
6. Phase 1 closeout proof rerun:
  - `python -m pytest tests/test_api.py tests/test_auth.py tests/test_relay_security.py tests/test_security_scan.py tests/test_service_auth_audit.py tests/02_RUNTIME/router/test_privacy.py tests/02_RUNTIME/api/test_api_endpoints.py -q`
  - Result: 139 passed in 10.42s
  - Reconciled verification-only files against `HEAD d4de95945d7aeb05a0721fcfafe5fe9679e6f10d`: `tests/test_auth.py` and `tests/test_service_auth_audit.py` are unchanged and were used as proof inputs only.
7. Phase 1 closeout scanner rerun:
  - `python scripts/service_auth_audit.py --json --save`
  - Result: overall risk LOW, 0 critical findings, timestamp `20260801T164449Z`
  - `python scripts/security_scan.py --json`
  - Result: passed, 0 high-severity findings
8. Phase 1 closeout diff hygiene:
  - `git diff --check`
  - Result: clean after removing the two trailing spaces from `docs/PRE_SESSION_AND_TOOLS.md:3`

## Closeout note outside Phase 1 scope
- `docs/PRE_SESSION_AND_TOOLS.md:3` no longer blocks `git diff --check`.
- That docs file remains outside the Phase 1 checkpoint commit even though the whitespace-only fix was required to run the closeout proof cleanly.

## Dependency-vulnerability remediation
- Replaced `python-jose>=3.3.0` with `PyJWT>=2.10.1` in `requirements.txt`.
- Updated `02_RUNTIME/api/auth.py` and the legacy API endpoint test harness to use the new JWT stack.
- Re-ran `python scripts/security_scan.py --json`.
- Result: dependency scan reports 0 vulnerabilities and the security gate passes.

## Files changed in this slice
- `02_RUNTIME/api/auth.py`
- `02_RUNTIME/api/main.py`
- `09_DEPLOYMENT/claude-relay/relay.py`
- `.github/workflows/ci.yml`
- `requirements.txt`
- `tests/test_api.py`
- `tests/test_relay_security.py`
- `tests/test_security_scan.py`
- `tests/02_RUNTIME/router/test_privacy.py`
- `tests/02_RUNTIME/api/test_api_endpoints.py`

## Phase boundary
Phase 1 security remediation is complete. Subsequent work should either:
- proceed to the next planned phase, or
- separately clear the non-security diff hygiene blocker if a fully unblocked benchmark result is required.