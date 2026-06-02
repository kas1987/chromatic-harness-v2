#!/usr/bin/env bash
# Federate routing governance from chromatic-harness-v2/docs/routing/ to consumers.
# Usage: bash scripts/federate-governance.sh [--dry-run]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/../docs/routing"
DRY_RUN="${1:-}"
ROUTING_FILES=(multi-router-matrix.yaml auto-mode-scope.yaml subagent-token-efficiency.md model-routing-for-subagents.md)
TARGETS=(/c/Users/kas41/.claude/governance /c/Users/kas41/.agents/governance)
WIKI_TARGET=/c/Users/kas41/chromatic-wiki/03_GOVERNANCE
for TARGET in "${TARGETS[@]}"; do
  mkdir -p "$TARGET"
  for FILE in "${ROUTING_FILES[@]}"; do
    [[ "$DRY_RUN" == "--dry-run" ]] && echo "[dry-run] $SRC/$FILE → $TARGET/$FILE" || cp -f "$SRC/$FILE" "$TARGET/$FILE"
  done
done
mkdir -p "$WIKI_TARGET"
cp -f "$SRC"/*.yaml "$SRC"/*.md "$WIKI_TARGET/" 2>/dev/null || true
echo "Federated to ${#TARGETS[@]} targets + wiki."
