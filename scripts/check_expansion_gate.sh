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

# Machine-verifiable spine check (bead chromatic-harness-v2-4do0): when a layer
# is named via SPINE_CHECK_LAYERS, verify it is actually wired in the codegraph
# (indexed symbols with edges), not just checkbox-claimed. Advisory unless
# SPINE_CHECK_STRICT=1. Never blocks the doc check above on its own.
if [ -n "${SPINE_CHECK_LAYERS:-}" ]; then
    spine_args=""
    [ "${SPINE_CHECK_STRICT:-0}" = "1" ] && spine_args="--strict"
    echo "EXPANSION_GATE: spine check for: $SPINE_CHECK_LAYERS"
    # shellcheck disable=SC2086
    if ! python "$REPO_ROOT/scripts/check_layer_spine.py" $spine_args $SPINE_CHECK_LAYERS; then
        echo "EXPANSION_GATE: FAIL: prerequisite layer(s) not wired in codegraph"
        fail=1
    fi
fi

if [ "$fail" -eq 0 ]; then
    echo "EXPANSION_GATE: PASS"
    exit 0
else
    exit 1
fi
