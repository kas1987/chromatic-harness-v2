#!/usr/bin/env bash
# check_expansion_gate.sh
# Binary pass/fail: verifies the expansion gate documents are present and non-empty.
# Exit 0 = PASS, Exit 1 = FAIL

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GATE_DOC="$REPO_ROOT/GOVERNANCE_EXPANSION_GATE.md"
MATRIX_DOC="$REPO_ROOT/VALIDATION_MATRIX.md"

fail=0

check_file() {
    local file="$1"
    local label="$2"
    if [ ! -f "$file" ]; then
        echo "EXPANSION_GATE: FAIL: missing $label"
        fail=1
    elif [ ! -s "$file" ]; then
        echo "EXPANSION_GATE: FAIL: empty $label"
        fail=1
    fi
}

check_file "$GATE_DOC" "GOVERNANCE_EXPANSION_GATE.md"
check_file "$MATRIX_DOC" "VALIDATION_MATRIX.md"

if [ "$fail" -eq 0 ]; then
    echo "EXPANSION_GATE: PASS"
    exit 0
else
    exit 1
fi
