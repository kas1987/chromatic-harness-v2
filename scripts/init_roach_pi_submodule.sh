#!/usr/bin/env bash
# Initialize roach-pi git submodule for Option C runtime.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .gitmodules ]]; then
  echo ".gitmodules missing — run from chromatic-harness-v2 root" >&2
  exit 1
fi

echo "Initializing submodule 02_RUNTIME/runtime-engines/roach-pi ..."
git submodule update --init --recursive 02_RUNTIME/runtime-engines/roach-pi

python scripts/roach_pi_status.py
echo "Done. Adapter uses stub mode until health markers exist."
