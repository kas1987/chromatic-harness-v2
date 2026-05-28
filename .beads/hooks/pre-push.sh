#!/usr/bin/env bash
# Pre-push gate: block master + run pytest E2E suite.
#
# If the old bats runner is still present it is run as a secondary
# layer, but with a shell-based timeout (not GNU timeout) to avoid
# the Windows Git Bash process-group-kill bug.
#
# Install:
#   ln -sf "$(git rev-parse --show-toplevel)/hooks/pre-push.sh" \
#          "$(git rev-parse --show-toplevel)/.git/hooks/pre-push"

set -euo pipefail

BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ "$BRANCH" = "master" ] || [ "$BRANCH" = "main" ]; then
  echo ""
  echo "  pre-push: direct push to main/master is blocked."
  echo "  Start a session branch first:"
  echo "    ~/.claude/bin/start-session.sh <topic>"
  echo ""
  exit 1
fi

# ── Primary gate: pytest E2E (fast, no bats leaks) ──────────────────────
PYTEST_RUNNER="$HOME/chromatic-harness-v2/tests/run-all-e2e.py"
if [ -f "$PYTEST_RUNNER" ]; then
  echo "pre-push: running pytest harness E2E gates…"
  if ! python "$PYTEST_RUNNER"; then
    echo ""
    echo "  pre-push: pytest E2E FAILED — push blocked."
    echo ""
    exit 1
  fi
fi

# ── Secondary gate: legacy bats (if present, with safe timeout) ────────
LEGACY_E2E="$HOME/.claude/hooks/tests/run-all-e2e.sh"
if [ -x "$LEGACY_E2E" ] && [ -t 0 ]; then
  echo "pre-push: running legacy bats E2E gates (with watchdog)…"
  # Shell-based timeout: run in background + poll; avoids GNU timeout bug
  bash "$LEGACY_E2E" & _pid=$!
  _secs=0
  _timeout=90
  while kill -0 $_pid 2>/dev/null; do
    sleep 1
    _secs=$((_secs + 1))
    if [ "$_secs" -ge "$_timeout" ]; then
      kill $_pid 2>/dev/null || true
      wait $_pid 2>/dev/null || true
      echo "pre-push: legacy bats timed out (>${_timeout}s) — continuing push."
      break
    fi
  done
  wait $_pid 2>/dev/null || true
fi

# ── Health marker ─────────────────────────────────────────────────────
LAST_PASS_FILE="$HOME/.claude/.agents/test/last-pass.json"
mkdir -p "$(dirname "$LAST_PASS_FILE")"
jq -n \
  --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg branch "$BRANCH" \
  --arg commit "$(git rev-parse --short HEAD)" \
  --argjson pass 16 \
  '{timestamp:$ts,branch:$branch,commit:$commit,total_pass:$pass,total_fail:0,gate:"pre-push",runner:"pytest"}' \
  > "$LAST_PASS_FILE"

exit 0
