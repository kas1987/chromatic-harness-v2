#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
args=(scripts/session_boot_automation.py --invoked-by scheduler)
[[ "${1:-}" == "--force" ]] && args+=(--force)
[[ "${1:-}" == "--full" || "${2:-}" == "--full" ]] && args+=(--full)
python "${args[@]}"
