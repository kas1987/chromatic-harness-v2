# Session Retrospective — PR #233 CI Fix & Gate Wrapper Root Cause

**Date:** 2026-06-02
**PRs merged:** #233, #234, #232, #231 (earlier in session)
**Branch:** `feat/w0wk-2-chromatic-envelope` → merged to `session/chromatic-harness-v2-initial`

## What shipped

- **PR #233** (`feat(schema): discriminated envelope + single validation path`): Discriminated envelope schema validation, `envelope_validator.py`, `validate_schema_registry.py` with `FormatChecker`, adapter `from exc` chaining, `jsonschema[format-nongpl]` requirement.
- **Gate CI fix** (`_impact_fan_out` wrapper): Replaced `_impact_fan_out = impact_fan_out` alias with a local wrapper that reads `router.pipeline.impact.IMPACT_ENABLED` dynamically, so `monkeypatch.setattr(impact_mod, "IMPACT_ENABLED", ...)` is visible to the gate. Seven `test_gate_impact_fanout` tests went from 2 failures → all green.

## Learnings

### 1. Module alias vs dynamic module attribute read — the monkeypatch visibility trap

`_impact_fan_out = impact_fan_out` binds gate's name to the pipeline function. That function reads `IMPACT_ENABLED` from its own module's globals. `monkeypatch.setattr(impact_mod, "IMPACT_ENABLED", True)` sets `router.pipeline.impact.IMPACT_ENABLED` — which the alias function sees when it executes, BUT the gate's own module-level `IMPACT_ENABLED = ...` import captured the original value at load time.

Fix: make the wrapper do `import router.pipeline.impact as _impact; if not _impact.IMPACT_ENABLED:` — this reads the live attribute from the module object at call time, so the monkeypatch is always observed.

**Rule:** Whenever a gate-level function needs to be test-patchable via monkeypatch on a sub-module attribute, the wrapper MUST read via the module object (`_impact.ATTR`), never via a gate-level name bound at import time.

### 2. Concurrent autonomous session causes commit-on-wrong-branch failures

The `auto/chromatic-harness-v2-u8uj.1` autonomous worker runs `task_runner.py` in the SHARED working directory and switches branches (~12+ times/hour). This caused:
- My Edit applied to gate.py → concurrent session switches branch → `git add` stages the wrong branch's file → commit lands with wrong content.
- Commits made after stash/checkout land on `feat/merge-gate-phase1` instead of `feat/w0wk-2-chromatic-envelope`.

**Workaround used:** `git checkout HEAD -- <file>` to reset working tree to committed state, re-apply edit, re-verify tests, re-commit.

**Root fix needed:** `task_runner.py` and `claude_delegate_gate.py` must use `git worktree add` to create isolated checkouts per task. See bead `concurrent-runner-worktree-isolation` memory.

### 3. Linter can rewrite a file between Edit and git add

A pre-commit linter or hook that reformats files in the working tree AFTER `git add` but before the commit doesn't affect the staged index — the commit captures what was staged. BUT if the linter fires BEFORE `git add`, the file gets overwritten and the next `git add` stages the linter's version, not the edit.

**Signal:** `git show HEAD:<file> | grep <expected>` returns the old content even though the Edit succeeded — means the linter ran between Edit and add.

**Defense:** After Edit, always run the test to confirm the change is live in the working tree before `git add`.

### 4. Cherry-pick vs direct edit when cherry-picking from wrong-branch commit

When a fix commit lands on the wrong branch (concurrent session switched it), cherry-pick works IF the base content matches. But if the target branch has diverged significantly (different _load_submodule impl, different import block), cherry-pick will conflict. Faster: just re-apply the edit directly on the target branch than resolving a cherry-pick conflict.

## KPI snapshot

| Metric | Value |
|--------|-------|
| `test_gate_impact_fanout` failures before | 2 |
| `test_gate_impact_fanout` failures after | 0 |
| Branch switches caused by concurrent session (reflog) | 12+ in last hour |
| Stale agent beads closed | 5 |

## Follow-up

- **Concurrent runner worktree isolation**: `02_RUNTIME/orchestrator/task_runner.py` and `scripts/claude_delegate_gate.py` need `git worktree add` so autonomous workers use isolated checkouts. This is the root cause of repeated wrong-branch commits. Track as new bead.
- **Merge queue**: PR #228, #232, #231 already merged. Review any remaining PRs in the session queue.
- Next: `bd ready`
