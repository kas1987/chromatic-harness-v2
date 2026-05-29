#!/usr/bin/env bash
# Sync lite Claude Code workflows from repo → ~/.claude/workflows/
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/.claude/workflows"
DEST="$HOME/.claude/workflows"
mkdir -p "$DEST"
for f in "$SRC"/*.js; do
  base="$(basename "$f")"
  if [[ -f "$DEST/$base" ]]; then
    cp "$DEST/$base" "$DEST/${base}.pre-sync.bak"
    echo "Backed up $base -> ${base}.pre-sync.bak"
  fi
  cp "$f" "$DEST/$base"
  echo "Installed $base"
done
echo ""
echo "Done. Heavy archived workflows (*.HEAVY.js.bak) are NOT installed."
echo "Read docs/AGENT_ANTIPATTERNS.md before running /ship or /qa."
