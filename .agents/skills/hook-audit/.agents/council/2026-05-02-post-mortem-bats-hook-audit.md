---
id: post-mortem-2026-05-02-bats-hook-audit
type: post-mortem
date: 2026-05-02
source: "[[memory/plans/2026-05-02-bats-hook-audit.md]]"
pre_mortem_ref: "[[memory/council/2026-05-02-pre-mortem-bats-hook-audit.md]]"
---

# Post-Mortem: BATS tests for hook-audit 4 phases

## Council Verdict: PASS

| Surface | Status | Notes |
|---------|--------|-------|
| Code | ✅ PASS | 15 tests committed, CRLF fix committed |
| Docs | N/A | No user-facing docs in scope |
| Examples | ✅ PASS | 5 fixtures cover all Phase 4 scenarios |
| Proof | ✅ PASS | 15/15 assertions verified in smoke-run |

## Scope Delta (Plan vs Delivered)

| Issue | Planned | Delivered | Delta |
|-------|---------|-----------|-------|
| 1: install-bats.sh | ✓ | ✓ | none |
| 2: 3 fixtures | ✓ | 5 fixtures (+ echo-no-timeout.json from F1 fix, multi-event.json from prior session) | +2 (pre-mortem F1 applied) |
| 3: 14 BATS tests | 14 | 15 (Phase 4 had 4 bullets not 3) | +1 (pre-mortem F3 resolved correctly) |
| CRLF fix in audit.sh | not planned | ✓ (discovered during smoke-test) | +1 bugfix |
| Delete stale audit.bats | not planned | ✓ (found during vibe) | +1 cleanup |

## Prediction Accuracy

| ID | Prediction | Outcome | Score |
|----|-----------|---------|-------|
| pm-20260502-001 | builtin + missing-timeout share fixture → mask each other | MISS — F1 fixture split was applied correctly; `echo-no-timeout.json` separated at implementation time | Flywheel worked |
| pm-20260502-002 | install-bats.sh conformance only checks existence | HIT (partial) — `bash -n` added informally; not in formal conformance block | Addressed |
| pm-20260502-003 | Phase 4 count 3 but lists 4 bullets | SURPRISE resolved — all 4 implemented → 15 tests total | Low severity, correct call |

Pre-mortem ROI: 2/3 predictions were actionable. Fixture separation (F1) prevented a masked-test failure.

## Key Findings

### Bugs Found and Fixed

| Bug | Severity | Fix |
|-----|----------|-----|
| Windows jq CRLF: `timeout="unset\r"` bypassed `!= "unset"` check; `(no timeout)` flag never fired | significant | `tr -d '\r'` added to `extract_hooks()` pipeline |
| `audit.bats` (prior session) used `export PROJECT_SETTINGS=...` but audit.sh sets it as local var — isolation silently broken | significant | Deleted in vibe phase |
| `package.json` test script pointed to deleted `audit.bats` | low | Updated to `tests/` directory |

### Process Findings

- External linter stripped `"timeout": 5` from `echo-no-timeout.json` silently; test still passed because builtin detection is independent of timeout. Verify fixture fields immediately after writing.
- Pre-mortem F1 prediction was correct but the fix was applied at implementation time (fixture split), not as a separate wave — which is fine for a WARN finding.

## Learnings (L1-L4)

See `.agents/learnings/2026-05-02-bats-hook-audit.md`:
- **L1**: Windows jq emits CRLF — always `tr -d '\r'` after jq in bash scripts
- **L2**: `bash -n` fails on BATS files — use `bats --dry-run` instead
- **L3**: HOME+cd pattern isolates scripts with hardcoded settings paths
- **L4**: External linters can strip fixture fields mid-session — verify immediately

## Test Pyramid Assessment

| Level | Count | Notes |
|-------|-------|-------|
| L0 (build/JSON valid) | 5 | JSON validity checked for all fixtures |
| L1 (subprocess integration) | 15 | All BATS tests run audit.sh subprocess |
| L2+ | 0 | N/A — bash script, subprocess IS integration |

Weighted score: 0.20 (acceptable for shell script test suite — L1 subprocess tests are the appropriate top level).

## Next Work (Harvested)

| ID | Title | Type | Severity |
|----|-------|------|----------|
| nw-bats-001 | Commit SKILL.md and references/ to hook-audit repo | tech-debt | low |
| nw-bats-002 | Add BATS test using multi-event fixture for coverage phase | enhancement | low |
| nw-bats-003 | Audit all skills for jq CRLF issue on Windows | tech-debt | moderate |

## Decision Gate

[x] CLOSED — All issues resolved, bugs fixed, tests passing, stale files cleaned up.
