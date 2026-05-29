#!/usr/bin/env bash
# Requires: git, internet access. Install target: /usr/local (adjustable via $1)
set -euo pipefail
DEST="${1:-/usr/local}"
TMP=$(mktemp -d)
git clone --depth 1 https://github.com/bats-core/bats-core.git "$TMP/bats-core"
"$TMP/bats-core/install.sh" "$DEST"
rm -rf "$TMP"
echo "bats installed: $(bats --version)"
