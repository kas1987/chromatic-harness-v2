# PDR: Post-Audit Remediation — Chromatic Harness v2

**PDR ID:** PDR-AUDIT-2026-05-28
**Date:** 2026-05-28
**Author:** TwistKS (agent session)
**Status:** Approved for implementation
**Related:** `.agents/audit/2026-05-28-harness-audit.md`

---

## 1. Executive Summary

The 2026-05-28 audit of Chromatic Harness v2 revealed a functional, tested codebase with critical hygiene gaps: zero measured coverage on `src/`, 53 ruff lint errors, 11 unformatted files, 7 duplicate beads issues, and 2 unpushed commits. This PDR defines the remediation scope, acceptance criteria, and execution order.

**Goal:** Bring the codebase to a ship-ready state: clean lint/format, meaningful coverage, deduplicated tracking, and a CI gate that prevents regression.

---

## 2. Audit Findings (Condensed)

| # | Finding | Severity | Owner |
|---|---------|----------|-------|
| A1 | `agentops-events.jsonl` still tracked despite gitignore | P0 | Infrastructure |
| A2 | 2 commits unpushed to origin | P0 | Infrastructure |
| A3 | 53 ruff lint errors (F401, E402, E741, E401, F841) | P1 | Code Quality |
| A4 | 11 files need `ruff format` | P1 | Code Quality |
| A5 | Coverage 0% on `src/chromatic_router/` — tests import from `02_RUNTIME/router/` | P1 | Testing |
| A6 | 1 unawaited coroutine warning in `test_openhuman_integration.py` | P1 | Testing |
| A7 | 7 duplicate beads smoke-test issues | P1 | Tracking |
| A8 | No CI workflow (GitHub Actions) | P2 | Infrastructure |
| A9 | Import strategy undocumented (`src/` vs `02_RUNTIME/`) | P2 | Documentation |
| A10 | No mypy type checking | P2 | Code Quality |

---

## 3. Remediation Strategy

### Wave 1 — Infrastructure (P0)
Clean git state so subsequent work can push cleanly.

1. **Untrack runtime logs** — `git rm --cached` on jsonl files now covered by `.gitignore`
2. **Push pending commits** — the 2 commits already on `session/chromatic-harness-v2-initial`

### Wave 2 — Code Hygiene (P1)
Fix all lint/format errors in one pass to avoid merge conflicts.

3. **Auto-fix ruff errors** — `ruff check --fix` resolves 15 of 53 (F401, F841, E401)
4. **Format all files** — `ruff format src/ tests/`
5. **Manual fix E741** — Replace ambiguous `l` with `line` in 4 locations across 3 test files
6. **Fix E402 / sys.path pattern** — Replace per-test `sys.path.insert` with `conftest.py` or `pytest.ini` `pythonpath`
7. **Fix unawaited coroutine** — Add `await` or fix mock in `test_openhuman_integration.py:196`

### Wave 3 — Coverage Alignment (P1)
Resolve the `src/` vs `02_RUNTIME/router/` ambiguity.

8. **Coverage path fix** — Either:
   - Option A: Repoint tests to import from `src.chromatic_router` (canonical package), OR
   - Option B: Add `02_RUNTIME/router/` to coverage map and document it as the test entrypoint
   
   **Decision:** Option A preferred — `src/chromatic_router/` is the installable package; `02_RUNTIME/router/` is the runtime working copy. Tests should exercise the canonical package.

### Wave 4 — Tracking Cleanup (P1)

9. **Deduplicate beads issues** — Close 6 of 7 identical smoke-test tasks, keep 1

### Wave 5 — CI & Documentation (P2)
Prevent regression and clarify architecture.

10. **Add GitHub Actions workflow** — `.github/workflows/ci.yml` running `ruff check`, `ruff format --check`, `pytest --cov`
11. **Document import strategy** — Add `docs/IMPORT_STRATEGY.md` clarifying `src/` vs `02_RUNTIME/router/`
12. **Add mypy** — Install `mypy`, run once, fix critical errors, add to CI

---

## 4. Acceptance Criteria

### Per-Wave Gates

| Wave | Gate | Check |
|------|------|-------|
| 1 | `git status` clean | `git status` shows nothing to commit, working tree clean |
| 1 | `git push` succeeds | `git status` shows "up to date with origin" |
| 2 | `ruff check src/ tests/` passes with 0 errors | Exit code 0 |
| 2 | `ruff format --check src/ tests/` passes | Exit code 0 |
| 3 | `pytest --cov=src/chromatic_router` shows >50% coverage | `coverage report` line coverage ≥ 50% |
| 4 | `bd list --status=in_progress` shows exactly 1 smoke-test issue | Count = 1 |
| 5 | CI passes on PR | GitHub Actions green |
| 5 | `mypy src/` passes with 0 critical errors | Exit code 0 or only `ignore`d issues |

### Final Gate

All of the above + `bd preflight` passes.

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------:|-------:|-----------|
| Repointing tests to `src/` breaks imports | Medium | High | Run full test suite after each file change; use `importlib.reload` sparingly |
| `conftest.py` refactor conflicts with existing test setup | Low | Medium | Keep existing `sys.path.insert` as fallback during transition, remove after verify |
| beads dedup closes wrong issue | Low | Low | Close with `--reason="duplicate"` so reversible |
| CI workflow fails on Windows paths | Medium | Medium | Test locally with `act` or push to feature branch first |

---

## 6. Dependencies

```
Wave 1 (Infrastructure)
  └─ must complete before Wave 2 (Code Hygiene)
      └─ must complete before Wave 3 (Coverage)
          └─ must complete before Wave 5 (CI)
Wave 4 (Tracking Cleanup)
  └─ independent, can run in parallel with Waves 2-3
```

---

## 7. Success Criteria

- `ruff check src/ tests/` → 0 errors
- `ruff format --check src/ tests/` → 0 changes
- `pytest --cov=src/chromatic_router` → ≥50% line coverage
- `bd list --status=in_progress` → 1 smoke-test issue (not 7)
- GitHub Actions CI green on every push
- `mypy src/` → 0 critical errors
- `bd preflight` passes

---

## 8. Out of Scope

- Refactoring adapter logic or runtime behavior
- Adding new features (new providers, new magnets)
- Performance optimization
- Security audit (separate epic)

---

*End of PDR. Proceed to `/plan` for beads issue creation and execution.*
