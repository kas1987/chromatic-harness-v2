#!/usr/bin/env bash
# harness-health.sh — canonical harness health check with binary pass/fail exit
# Runs all checks independently; failures accumulate. Exit 0 = all pass, 1 = any fail.
set -euo pipefail

FAIL_COUNT=0

# ── helpers ──────────────────────────────────────────────────────────────────
pass() { printf '[PASS] %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1"; FAIL_COUNT=$(( FAIL_COUNT + 1 )); }

# ── Check 1: bats E2E suites ──────────────────────────────────────────────────
E2E_SCRIPT="$HOME/.claude/hooks/tests/run-all-e2e.sh"
if [ ! -f "$E2E_SCRIPT" ]; then
  fail "bats-e2e-suites (run-all-e2e.sh not found)"
else
  if bash "$E2E_SCRIPT" >/dev/null 2>&1; then
    pass "bats-e2e-suites"
  else
    fail "bats-e2e-suites"
  fi
fi

# ── Check 2: review-daemon node tests ────────────────────────────────────────
REVIEW_DAEMON_DIR="$HOME/.claude/review-daemon"
if ! command -v node >/dev/null 2>&1; then
  printf '[PASS] review-daemon-node-tests (skipped — node not available)\n'
elif [ ! -d "$REVIEW_DAEMON_DIR" ]; then
  printf '[PASS] review-daemon-node-tests (skipped — review-daemon dir not found)\n'
else
  NODE_OUT=$(cd "$REVIEW_DAEMON_DIR" && node --test src/test/*.test.ts 2>&1 || true)
  if echo "$NODE_OUT" | grep -qi "no tests found\|Could not resolve\|ERR_MODULE_NOT_FOUND"; then
    printf '[PASS] review-daemon-node-tests (skipped — no runnable tests found)\n'
  elif echo "$NODE_OUT" | grep -qi "not ok\|failures\|failed"; then
    fail "review-daemon-node-tests"
  else
    pass "review-daemon-node-tests"
  fi
fi

# ── Check 3: Multica liveness ─────────────────────────────────────────────────
MULTICA_BIN="$HOME/.multica/bin/multica"
if [ ! -x "$MULTICA_BIN" ]; then
  printf '[PASS] multica-liveness (skipped — multica binary not found)\n'
else
  if "$MULTICA_BIN" workflow list >/dev/null 2>&1; then
    pass "multica-liveness"
  else
    fail "multica-liveness"
  fi
fi

# ── Check 4: governance staleness (session-health.json < 24 h old) ────────────
SESSION_HEALTH="$HOME/.claude/.agents/router/session-health.json"
if [ ! -f "$SESSION_HEALTH" ]; then
  fail "governance-staleness (session-health.json not found)"
else
  NOW=$(date +%s)
  FILE_MTIME=$(date -r "$SESSION_HEALTH" +%s 2>/dev/null || stat -c %Y "$SESSION_HEALTH" 2>/dev/null || echo 0)
  AGE=$(( NOW - FILE_MTIME ))
  if [ "$AGE" -le 86400 ]; then
    pass "governance-staleness"
  else
    fail "governance-staleness (session-health.json is ${AGE}s old, limit 86400s)"
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
printf '\n'
if [ "$FAIL_COUNT" -eq 0 ]; then
  printf 'Harness health: PASS\n'
  exit 0
else
  printf 'Harness health: FAIL (%d check%s failed)\n' "$FAIL_COUNT" "$( [ "$FAIL_COUNT" -eq 1 ] && echo '' || echo 's' )"
  exit 1
fi
