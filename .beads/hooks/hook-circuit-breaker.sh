#!/usr/bin/env bash
# hook-circuit-breaker.sh — Universal hook wrapper: timeout, failure counter, auto-disable, fallback
# Usage: hook-circuit-breaker.sh <hook-name> <actual-command...>
#
# State dir: ~/.claude/.agents/circuit-breaker/
#   <hook-name>.failures   — consecutive failure count
#   <hook-name>.disabled   — touch to auto-disable (circuit open)
#   <hook-name>.last-ms    — last invocation duration in ms
#
# Circuit breaker rules:
#   - If .disabled file exists → skip immediately (exit 0)
#   - If failures >= 3 → create .disabled, skip (exit 0)
#   - Timeout enforced by caller-supplied TIMEOUT env var (default 8s)
#   - On success: reset failure count to 0
#   - On failure/timeout: increment failure count
#   - Always exit 0 (fail-open) — never block the parent hook chain
#
# Self-health: writes <hook-name>.last-ms and .status after each invocation
#   .status values: ok | timeout | fail | circuit-open

set -uo pipefail

CB_DIR="${CB_DIR:-${HOME}/.claude/.agents/circuit-breaker}"
mkdir -p "${CB_DIR}" 2>/dev/null || true

HOOK_NAME="$1"
shift
ACTUAL_CMD=("$@")
TIMEOUT_SECS="${TIMEOUT_SECS:-8}"

# ── Circuit open check ───────────────────────────────────────────────────────
if [ -f "${CB_DIR}/${HOOK_NAME}.disabled" ]; then
  printf '%s' "circuit-open" > "${CB_DIR}/${HOOK_NAME}.status" 2>/dev/null || true
  exit 0
fi

FAIL_FILE="${CB_DIR}/${HOOK_NAME}.failures"
FAIL_COUNT=0
if [ -f "${FAIL_FILE}" ]; then
  FAIL_COUNT=$(cat "${FAIL_FILE}" 2>/dev/null | tr -d '[:space:]')
  FAIL_COUNT=${FAIL_COUNT:-0}
fi

# ── Already at threshold → trip circuit ──────────────────────────────────────
if [ "${FAIL_COUNT}" -ge 3 ]; then
  touch "${CB_DIR}/${HOOK_NAME}.disabled" 2>/dev/null || true
  printf '%s' "circuit-open" > "${CB_DIR}/${HOOK_NAME}.status" 2>/dev/null || true
  exit 0
fi

# ── Execute with timeout ─────────────────────────────────────────────────────
START_NS=$(date +%s%N 2>/dev/null || python3 -c "import time; print(int(time.time()*1e9))" 2>/dev/null || echo 0)

OUTPUT=$(timeout "${TIMEOUT_SECS}" bash -c '${ACTUAL_CMD[@]}' 2>&1) || true
RC=$?

END_NS=$(date +%s%N 2>/dev/null || python3 -c "import time; print(int(time.time()*1e9))" 2>/dev/null || echo 0)
ELAPSED_MS=$(( (END_NS - START_NS) / 1000000 ))
[ "${ELAPSED_MS}" -lt 0 ] && ELAPSED_MS=0

printf '%d' "${ELAPSED_MS}" > "${CB_DIR}/${HOOK_NAME}.last-ms" 2>/dev/null || true

# ── Result handling ───────────────────────────────────────────────────────────
if [ $RC -eq 124 ]; then
  # Timed out
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '%d' "${FAIL_COUNT}" > "${FAIL_FILE}" 2>/dev/null || true
  printf '%s' "timeout" > "${CB_DIR}/${HOOK_NAME}.status" 2>/dev/null || true
  # Emit warning only on first timeout (avoid log spam)
  [ "${FAIL_COUNT}" -eq 1 ] && printf '[CIRCUIT-BREAKER] %s timed out (%dms, fail #%d)\n' "${HOOK_NAME}" "${ELAPSED_MS}" "${FAIL_COUNT}" >&2 || true
elif [ $RC -ne 0 ]; then
  # Failed
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '%d' "${FAIL_COUNT}" > "${FAIL_FILE}" 2>/dev/null || true
  printf '%s' "fail" > "${CB_DIR}/${HOOK_NAME}.status" 2>/dev/null || true
  [ "${FAIL_COUNT}" -eq 1 ] && printf '[CIRCUIT-BREAKER] %s failed exit=%d (%dms, fail #%d)\n' "${HOOK_NAME}" "$RC" "${ELAPSED_MS}" "${FAIL_COUNT}" >&2 || true
else
  # Success
  printf '0' > "${FAIL_FILE}" 2>/dev/null || true
  printf '%s' "ok" > "${CB_DIR}/${HOOK_NAME}.status" 2>/dev/null || true
  # Pass through stdout only on success (avoid noise from failing hooks)
  printf '%s' "$OUTPUT"
fi

exit 0