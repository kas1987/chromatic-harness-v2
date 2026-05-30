#!/usr/bin/env bash
# Optional bash wrapper. Canonical wiring: .claude/settings.json SessionEnd → session_closeout.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export CHROMATIC_REPO="$ROOT"
python scripts/session_closeout.py --invoked-by claude_code "$@" || true
exit 0
