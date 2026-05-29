---
date: 2026-05-02
target: hook-audit BATS test suite
verdict: WARN → PASS (issues fixed inline)
---

# Vibe Report: hook-audit BATS test suite

## Complexity Analysis

| File | Size | Rating |
|------|------|--------|
| `scripts/audit.sh` | 339 lines | B — moderate (4 phase functions, no deep nesting) |
| `tests/hook-audit.bats` | 127 lines, 15 tests | A — simple (avg 8 lines/test) |
| `tests/install-bats.sh` | 9 lines | A — trivial |

No complexity hotspots. Language: shell/bash — radon/gocyclo not applicable.

## Test Pyramid

| Level | Count | Weight | Contribution |
|-------|-------|--------|--------------|
| L0 (build/syntax) | 5 (JSON valid + bash -n) | 1x | 5 |
| L1 (subprocess integration) | 15 BATS tests | 1x | 15 |
| L2+ | 0 | — | 0 |
| **Total** | **20** | | **20 / 100 = 0.20** |

WARN: weighted_score 0.20 < 0.3. However for a bash script under test via subprocess, L1 integration-via-subprocess IS the appropriate top level — L2/L3 (E2E) would be redundant. Acceptable for this scope.

## Findings

### F1 — Stale broken test file (SIGNIFICANT → FIXED)

`tests/audit.bats` from prior session used `export PROJECT_SETTINGS=...` to isolate tests. `audit.sh` sets `PROJECT_SETTINGS` as a local variable (line 19) and ignores env, so isolation was silently broken. Multiple tests in `audit.bats` would read the real project `.claude/settings.json`, giving non-deterministic results.

**Fix applied:** Deleted `tests/audit.bats`.

### F2 — echo-no-timeout.json linter modification (LOW → ACCEPTED)

External linter removed `timeout: 5` from `echo-no-timeout.json`, making it a catch-all PostToolUse with no timeout. This blurs the fixture separation from pre-mortem F1 (builtin test vs timeout test). However:
- `verify_marks_builtin` still asserts `✅(builtin)` ✓  
- `verify_flags_missing_timeout` uses `missing-script.json` (correct isolation maintained) ✓  
- Both tests pass against current fixture state ✓

**Fix:** Accepted. Fixture name is now literally accurate ("echo with no timeout").

### F3 — multi-event.json unused fixture (LOW → NOTED)

`tests/fixtures/multi-event.json` (SessionStart + PreToolUse + Stop) exists from prior session but is not referenced by `hook-audit.bats`. Not harmful. Could improve `coverage_marks_covered_event` test (currently asserts any ✅, could assert specific events covered).

**Fix:** Not fixed — test coverage is sufficient without it.

### F4 — CRLF fix in audit.sh (IMPROVEMENT → SHIPPED)

Windows/Git Bash jq emits `\r\n`. Without `tr -d '\r'`, `timeout="unset\r"` passes the `!= "unset"` check and the no-timeout flag never fires. Fix added `| tr -d '\r'` to `extract_hooks()` output. Verified: `(no timeout)` now correctly appears in verify output.

## Council Verdict: WARN → PASS

| Finding | Severity | Status |
|---------|----------|--------|
| Stale `audit.bats` with broken isolation | significant | FIXED (deleted) |
| CRLF bug in `extract_hooks` | significant | FIXED |
| `echo-no-timeout.json` linter modification | low | accepted |
| `multi-event.json` unused fixture | low | noted |

## Test Results (pre-ship gate)

```
inventory_heading_present:    PASS
inventory_marks_present_file: PASS
inventory_marks_missing_file: PASS
inventory_shows_hook_row:     PASS
coverage_heading_present:     PASS
coverage_marks_covered_event: PASS
coverage_warns_catchall:      PASS
cost_heading_present:         PASS
cost_shows_fires_column:      PASS
verify_heading_present:       PASS
verify_marks_missing_script:  PASS
verify_marks_builtin:         PASS
verify_flags_missing_timeout: PASS
unknown_phase_exits_nonzero:  PASS
all_phases_runs_all_headings: PASS
15/15 PASS
```

## Recommendation

[x] SHIP — All significant issues fixed inline. 15/15 assertions verified. BATS install required once (`bash tests/install-bats.sh`) to run the full suite.
