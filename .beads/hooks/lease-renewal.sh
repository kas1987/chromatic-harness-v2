#!/usr/bin/env bash
# PostToolUse hook: renew workstream lease on git commit.
#
# Trigger: fires after every Bash tool call. If the Bash command was a
# `git commit` AND a CLAUDE_RPI_EPIC env var is set, bump that workstream's
# lease_expires_at to now + 24h via workstream_registry.py.
#
# Best-effort: ALWAYS exits 0 — never blocks a tool call.
#
# Bypass: CLAUDE_LEASE_RENEWAL_DISABLE=1 → exit 0 immediately.

set +e

# Always-pass bypass
if [ "${CLAUDE_LEASE_RENEWAL_DISABLE:-0}" = "1" ]; then
  exit 0
fi

# Read PostToolUse JSON from stdin
input=$(cat 2>/dev/null || true)
if [ -z "$input" ]; then
  exit 0
fi

# Need jq for safe JSON parsing; if missing, exit cleanly
if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null)
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
case "$cmd" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

# Epic context required
if [ -z "${CLAUDE_RPI_EPIC:-}" ]; then
  exit 0
fi

# Locate workstream_registry.py
reg_path=""
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -f "${CLAUDE_PROJECT_DIR}/01_HARNESS/workstream_registry.py" ]; then
  reg_path="${CLAUDE_PROJECT_DIR}/01_HARNESS/workstream_registry.py"
elif [ -f "/c/Repos/Poly-Chromatic/prism-autonomy-harness/01_HARNESS/workstream_registry.py" ]; then
  reg_path="/c/Repos/Poly-Chromatic/prism-autonomy-harness/01_HARNESS/workstream_registry.py"
elif [ -f "C:/Repos/Poly-Chromatic/prism-autonomy-harness/01_HARNESS/workstream_registry.py" ]; then
  reg_path="C:/Repos/Poly-Chromatic/prism-autonomy-harness/01_HARNESS/workstream_registry.py"
fi

if [ -z "$reg_path" ]; then
  exit 0
fi

# Pick a python interpreter
py=""
for cand in python3 python py; do
  if command -v "$cand" >/dev/null 2>&1; then
    py="$cand"
    break
  fi
done
if [ -z "$py" ]; then
  exit 0
fi

# Best-effort renewal — swallow output and never fail
"$py" "$reg_path" renew --epic "$CLAUDE_RPI_EPIC" >/dev/null 2>&1 || true

exit 0
