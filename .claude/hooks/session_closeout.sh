#!/usr/bin/env bash
# Claude Code SessionEnd — repo-owned closeout (wire in ~/.claude/settings.json or project settings).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export CHROMATIC_REPO="$ROOT"
python scripts/session_closeout.py --invoked-by claude_code "$@" || true
exit 0
