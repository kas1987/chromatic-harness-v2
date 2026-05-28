#!/usr/bin/env bash
# Block direct pushes to master. Work on session/* branches instead.
# Activated globally via: git config --global core.hooksPath ~/.claude/hooks/
# Entrypoint: ~/.claude/hooks/pre-push (delegator) → this file

set -euo pipefail

BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ "$BRANCH" = "master" ]; then
  echo ""
  echo "  pre-push: direct push to master is blocked."
  echo "  Start a session branch first:"
  echo "    ~/.claude/bin/start-session.sh <topic>"
  echo "  Then open a PR when done:"
  echo "    gh pr create --draft"
  echo ""
  exit 1
fi

E2E_RUNNER="$HOME/.claude/hooks/tests/run-all-e2e.sh"
if [ -x "$E2E_RUNNER" ]; then
  export PATH="$HOME/.local/bin:$PATH"
  echo "pre-push: running harness E2E gates…"
  if ! bash "$E2E_RUNNER"; then
    echo ""
    echo "  pre-push: E2E suite FAILED — push blocked."
    echo "  Fix failing tests before pushing."
    echo ""
    exit 1
  fi
  # Write last-pass marker so Director gate dashboards can query harness health.
  LAST_PASS_FILE="$HOME/.claude/.agents/test/last-pass.json"
  mkdir -p "$(dirname "$LAST_PASS_FILE")"
  total_pass=$(jq -r '.total_pass // 0' "$LAST_PASS_FILE" 2>/dev/null || echo 0)
  jq -n \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg branch "$(git rev-parse --abbrev-ref HEAD)" \
    --arg commit "$(git rev-parse --short HEAD)" \
    --argjson pass "$total_pass" \
    '{timestamp:$ts,branch:$branch,commit:$commit,total_pass:$pass,total_fail:0,gate:"pre-push"}' \
    > "$LAST_PASS_FILE"
fi

exit 0
