# Chromatic Harness v2 — Audit Report

**Date:** 2026-05-28
**Auditor:** TwistKS (agent session)
**Branch:** `session/chromatic-harness-v2-initial`

---

## Executive Summary

| Category | Score | Notes |
|----------|-------|-------|
| Tests | ✅ 70/70 pass | 1 unawaited coroutine warning |
| Code Coverage | ⚠️ 0% (src/) | Tests import from `02_RUNTIME/router/` not `src/chromatic_router/` |
| Lint (ruff) | ❌ 53 errors | Mostly E402 (sys.path imports), F401 (unused), E741 (`l` var) |
| Format | ❌ 11 files need reformat | `ruff format --check` fails |
| Beads Health | ⚠️ 7 in_progress duplicates | All 7 are identical smoke-test tasks; 25 closed, 0 open |
| Git Sync | ⚠️ 2 commits ahead | Unpushed to origin; 1 untracked runtime log |
| Beads Remote | ✅ Configured | `origin` dolt remote added today |
| Pre-push Hook | ✅ Fixed | Shell-native timeout replaced GNU timeout abort |

**Overall verdict:** Functional and tested, but needs hygiene pass (lint/format) and coverage path alignment before next release.

---

## 1. Test Suite

```
platform win32 -- Python 3.12.3, pytest-9.0.2
70 passed, 1 warning in 3.92s
```

**Warning:**
- `tests/test_openhuman_integration.py:196` — `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited`

**Fix:** Add `await` to the mocked `adapter.complete()` call in the test, or remove async mocking if the method is sync.

---

## 2. Code Coverage

Coverage is **0% on `src/chromatic_router/`** because all tests use `sys.path.insert(0, str(_REPO / "02_RUNTIME"))` and import `router.*` directly from `02_RUNTIME/router/`. The `src/chromatic_router/` package is orphaned.

**Action required:**
1. Either repoint tests to import from `src.chromatic_router` (preferred)
2. Or remove `src/` if `02_RUNTIME/router/` is the canonical source
3. Or add `02_RUNTIME/router/` to the coverage map: `--cov=02_RUNTIME/router`

---

## 3. Lint Errors (53 total)

### Fixable automatically (15 via `ruff check --fix`):
- **F401** × 9 — Unused imports (`RouteUsage`, `SelectionResult`, `pytest`, `pathlib.Path`, `GovernanceRule`, `ScopeBaseline`, `ScopeCheckResult`, `ConfidenceBand`)
- **F841** × 1 — Unused variable `resp` in `test_router_gates.py:183`
- **E401** × 2 — Multiple imports on one line (`httpx, time`; `json, datetime`)

### Requires manual fix:
- **E402** × 35 — Module-level imports not at top of file (all due to `sys.path.insert` before imports)
- **E741** × 4 — Ambiguous variable name `l` (list comprehensions in 3 test files)

**Recommendation:** Replace `sys.path.insert` pattern with a `conftest.py` that adds `02_RUNTIME` to `PYTHONPATH`, or use `pytest` with `-p no:cacheprovider` and a project-level `pytest.ini` setting `pythonpath = 02_RUNTIME`.

---

## 4. Formatting

11 files need reformat:
- `src/chromatic_router/__init__.py`
- `src/chromatic_router/adapters/*.py` (6 files)
- `tests/run-all-e2e.py`
- `tests/test_complexity_and_routing.py`
- `tests/test_openhuman_boundary.py`
- `tests/test_system_memory.py`

**Fix:** `ruff format src/ tests/`

---

## 5. Beads Health

| Metric | Value |
|--------|-------|
| Total issues | 32 |
| Open | 0 |
| In Progress | 7 |
| Closed | 25 |
| Ready to work | 0 |

**Critical finding:** All 7 `in_progress` issues are **identical**:
- Title: "docker compose up -d to smoke-test the running stack end-to-end"
- IDs: `chromatic-harness-v2-6kt`, `-8p7`, `-gck`, `-i1c`, `-lso`, `-nm3`, `-vzr`

**This is a bug in issue creation** — the same task was created 7 times instead of once. All but one should be closed as duplicates.

**Action:**
```bash
cd chromatic-harness-v2
# Close 6 as duplicates, keep 1
bd update chromatic-harness-v2-6kt --claim
bd close chromatic-harness-v2-8p7 --reason="duplicate of chromatic-harness-v2-6kt"
# ... repeat for other 5
```

---

## 6. Git Status

```
On branch session/chromatic-harness-v2-initial
Your branch is ahead of 'origin/session/chromatic-harness-v2-initial' by 2 commits.

Changes not staged for commit:
    modified: 05_FRONTEND_CONSOLE/10_RUNTIME/logs/agentops-events.jsonl
```

- **2 commits unpushed** — includes the latest `.gitignore` fix for runtime logs
- **1 unstaged file** — `agentops-events.jsonl` (should now be gitignored after latest commit, but still tracked in working tree)

**Fix:**
```bash
git rm --cached 05_FRONTEND_CONSOLE/10_RUNTIME/logs/agentops-events.jsonl
git commit -m "chore: untrack runtime event logs now covered by gitignore"
git push
```

---

## 7. Beads Remote Sync

- **Dolt remote:** `origin → git+https://github.com/kas1987/chromatic-harness-v2.git` ✅
- **Status:** No pending dolt commits to push
- **Next:** After closing the duplicate issues, run `bd dolt push`

---

## 8. Governance / Hooks

| Hook | Status |
|------|--------|
| Pre-push E2E runner | ✅ Fixed — shell-native timeout (no GNU timeout abort) |
| `run-all-e2e.sh` | ✅ Passes all 70 tests |
| Policy gate (`policy_gate.py`) | ✅ Wired as PreToolUse Bash hook |
| `model-router.sh` | ✅ Ollama-down logic with vLLM fallback |

---

## 9. Recommendations (Priority Order)

### P0 — Before next push
1. **Untrack `agentops-events.jsonl`** — `git rm --cached` + commit + push
2. **Push the 2 unpushed commits** to origin

### P1 — This week
3. **Fix ruff lint errors** — run `ruff check --fix` for 15 auto-fixable, then manually fix E741 (`l` → `line`) and E402 (use `conftest.py` or `pytest.ini` `pythonpath`)
4. **Run `ruff format`** on `src/` and `tests/`
5. **Fix test coverage path** — either repoint tests to `src.chromatic_router` or add `02_RUNTIME/router/` to coverage map
6. **Close 6 duplicate beads issues** — keep 1 smoke-test task, close rest as duplicates

### P2 — Next sprint
7. **Add CI workflow** (GitHub Actions) that runs `ruff check`, `ruff format --check`, `pytest --cov`
8. **Document import strategy** — clarify whether `src/chromatic_router/` or `02_RUNTIME/router/` is canonical
9. **Add mypy** to `requirements.txt` and run type checks

---

## Quick Fix Commands

```bash
cd chromatic-harness-v2

# 1. Untrack runtime logs
git rm --cached 05_FRONTEND_CONSOLE/10_RUNTIME/logs/agentops-events.jsonl
git commit -m "chore: untrack runtime logs now covered by gitignore"

# 2. Auto-fix lint
ruff check --fix src/ tests/

# 3. Format everything
ruff format src/ tests/

# 4. Fix remaining E741 manually (replace `l` with `line` in 4 places)
# tests/test_kimi_and_governance.py:109
# tests/test_router_gates.py:214
# tests/test_system_memory.py:60, 65

# 5. Push
git push

# 6. Deduplicate beads issues
for id in chromatic-harness-v2-8p7 chromatic-harness-v2-gck chromatic-harness-v2-i1c chromatic-harness-v2-lso chromatic-harness-v2-nm3 chromatic-harness-v2-vzr; do
  bd close "$id" --reason="duplicate of chromatic-harness-v2-6kt"
done

# 7. Push beads data
bd dolt push
```

---

*End of audit. Run `bd preflight` after fixes to validate PR readiness.*
