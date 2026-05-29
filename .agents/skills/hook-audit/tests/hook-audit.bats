#!/usr/bin/env bats
AUDIT_SH="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/audit.sh"
FIXTURES_DIR="$(dirname "$BATS_TEST_FILENAME")/fixtures"

setup() {
  TEST_HOME=$(mktemp -d)
  TEST_PROJECT=$(mktemp -d)
  export HOME="$TEST_HOME"
  mkdir -p "$TEST_HOME/.claude"
  mkdir -p "$TEST_PROJECT/.claude"
  _orig_pwd="$PWD"
  cd "$TEST_PROJECT"
}

teardown() {
  cd "$_orig_pwd"
  rm -rf "$TEST_HOME" "$TEST_PROJECT"
}

# ── Phase 1: Inventory ──────────────────────────────────────────────────────

@test "inventory_heading_present" {
  run bash "$AUDIT_SH" --phase=inventory
  [ "$status" -eq 0 ]
  [[ "$output" == *"## Phase 1: Inventory"* ]]
}

@test "inventory_marks_present_file" {
  cp "$FIXTURES_DIR/pretools-hook.json" "$TEST_HOME/.claude/settings.json"
  run bash "$AUDIT_SH" --phase=inventory
  [ "$status" -eq 0 ]
  [[ "$output" == *"✅"* ]]
}

@test "inventory_marks_missing_file" {
  run bash "$AUDIT_SH" --phase=inventory
  [ "$status" -eq 0 ]
  [[ "$output" == *"❌"* ]]
}

@test "inventory_shows_hook_row" {
  cp "$FIXTURES_DIR/pretools-hook.json" "$TEST_PROJECT/.claude/settings.json"
  run bash "$AUDIT_SH" --phase=inventory
  [ "$status" -eq 0 ]
  [[ "$output" == *"PreToolUse"* ]]
}

# ── Phase 2: Coverage Analysis ──────────────────────────────────────────────

@test "coverage_heading_present" {
  run bash "$AUDIT_SH" --phase=coverage
  [ "$status" -eq 0 ]
  [[ "$output" == *"## Phase 2: Coverage Analysis"* ]]
}

@test "coverage_marks_covered_event" {
  cp "$FIXTURES_DIR/pretools-hook.json" "$TEST_HOME/.claude/settings.json"
  run bash "$AUDIT_SH" --phase=coverage
  [ "$status" -eq 0 ]
  [[ "$output" == *"✅"* ]]
}

@test "coverage_warns_catchall" {
  cp "$FIXTURES_DIR/catchall-posttools.json" "$TEST_PROJECT/.claude/settings.json"
  run bash "$AUDIT_SH" --phase=coverage
  [ "$status" -eq 0 ]
  [[ "$output" == *"Catch-all PostToolUse detected"* ]]
}

# ── Phase 3: Cost Profile ───────────────────────────────────────────────────

@test "cost_heading_present" {
  run bash "$AUDIT_SH" --phase=cost
  [ "$status" -eq 0 ]
  [[ "$output" == *"## Phase 3: Cost Profile"* ]]
}

@test "cost_shows_fires_column" {
  run bash "$AUDIT_SH" --phase=cost
  [ "$status" -eq 0 ]
  [[ "$output" == *"fires/session"* ]]
}

# ── Phase 4: Verification ───────────────────────────────────────────────────

@test "verify_heading_present" {
  run bash "$AUDIT_SH" --phase=verify
  [ "$status" -eq 0 ]
  [[ "$output" == *"## Phase 4: Verification"* ]]
}

@test "verify_marks_missing_script" {
  cp "$FIXTURES_DIR/missing-script.json" "$TEST_HOME/.claude/settings.json"
  run bash "$AUDIT_SH" --phase=verify
  [ "$status" -eq 0 ]
  [[ "$output" == *"❌ missing"* ]]
}

@test "verify_marks_builtin" {
  cp "$FIXTURES_DIR/echo-no-timeout.json" "$TEST_HOME/.claude/settings.json"
  run bash "$AUDIT_SH" --phase=verify
  [ "$status" -eq 0 ]
  [[ "$output" == *"✅(builtin)"* ]]
}

@test "verify_flags_missing_timeout" {
  cp "$FIXTURES_DIR/missing-script.json" "$TEST_HOME/.claude/settings.json"
  run bash "$AUDIT_SH" --phase=verify
  [ "$status" -eq 0 ]
  [[ "$output" == *"(no timeout)"* ]]
}

# ── Multi-event fixture ─────────────────────────────────────────────────────

@test "fixture_multi_event_json_exists" {
  [ -f "$FIXTURES_DIR/multi-event.json" ]
}

@test "coverage_sessionstart_covered_via_multi_event" {
  cp "$FIXTURES_DIR/multi-event.json" "$TEST_HOME/.claude/settings.json"
  run bash "$AUDIT_SH" --phase=coverage
  [ "$status" -eq 0 ]
  [[ "$output" == *"SessionStart"* ]]
  [[ "$output" == *"✅"* ]]
}

# ── Syntax / L0 ──────────────────────────────────────────────────────────────

@test "audit_sh_syntax_check" {
  run bash -n "$AUDIT_SH"
  [ "$status" -eq 0 ]
}


# ── Error paths ─────────────────────────────────────────────────────────────

@test "unknown_phase_exits_nonzero" {
  run bash "$AUDIT_SH" --phase=bogus
  [ "$status" -eq 1 ]
}

@test "all_phases_runs_all_headings" {
  run bash "$AUDIT_SH"
  [ "$status" -eq 0 ]
  [[ "$output" == *"## Phase 1: Inventory"* ]]
  [[ "$output" == *"## Phase 2: Coverage Analysis"* ]]
  [[ "$output" == *"## Phase 3: Cost Profile"* ]]
  [[ "$output" == *"## Phase 4: Verification"* ]]
}
