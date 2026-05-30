#!/usr/bin/env bash
# Full pre-session: automated boot + bd ready.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STRICT_MCP=0
FORCE=0
FULL=0
for arg in "$@"; do
  case "$arg" in
    --strict-mcp) STRICT_MCP=1 ;;
    --force) FORCE=1 ;;
    --full) FULL=1 ;;
  esac
done

failed=0
run_step() {
  local name="$1"
  shift
  echo ""
  echo "=== $name ==="
  if ! python "$@"; then
    echo "WARNING: $name failed" >&2
    failed=1
  fi
}

boot_args=(scripts/session_boot_automation.py --invoked-by preflight)
[[ "$FORCE" -eq 1 ]] && boot_args+=(--force)
[[ "$FULL" -eq 1 ]] && boot_args+=(--full)
run_step session_boot_automation "${boot_args[@]}"

if [[ "$STRICT_MCP" -eq 1 ]]; then
  run_step audit_mcp_strict scripts/audit_mcp_context.py --profile harness_dev --strict
fi

echo ""
echo "=== bd ready ==="
if command -v bd >/dev/null 2>&1; then
  bd ready || failed=1
else
  echo "WARNING: bd not available" >&2
fi

MANIFEST="$REPO_ROOT/07_LOGS_AND_AUDIT/pre_session/latest.json"
if [[ -f "$MANIFEST" ]]; then
  echo ""
  echo "Manifest: $MANIFEST"
else
  echo "WARNING: Manifest not written: $MANIFEST" >&2
  failed=1
fi

if [[ "$failed" -ne 0 ]]; then
  exit 1
fi
echo ""
echo "Preflight complete."
