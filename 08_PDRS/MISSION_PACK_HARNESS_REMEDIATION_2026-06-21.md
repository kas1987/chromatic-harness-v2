# Mission Pack — Harness V2 Remediation & Hardening
**Date:** 2026-06-21 · **Branch:** `feature/harness-finalization-2026-06-20` · **Status:** Active

> Resolve all SWOT findings, security threats, coverage gaps, and doc-sprawl surfaced by the 2026-06-21 audit. Bring local `main` in sync with origin and establish automated hygiene enforcement.

---

## Mission Index

| ID | Mission | Priority | Phase | Status |
|----|---------|----------|-------|--------|
| M-01 | Rotate leaked GitHub token | P0 | 0 | Open |
| M-02 | Fix syntax error in `rudalo_migration_audit.py` | P0 | 0 | Open |
| M-03 | Push `main` to origin (13 commits behind) | P1 | 1 | Open |
| M-04 | Fix pytest environment (hydra-core/antlr4 mismatch) | P1 | 1 | Open |
| M-05 | Update stale `ARTIFACT_MANIFEST.json` entry | P1 | 1 | Open |
| M-06 | Delete stale local branches | P1 | 1 | Open |
| M-07 | Runtime module test coverage sprint (30 gaps) | P2 | 2 | Open |
| M-08 | Scripts test coverage sprint (139 gaps) | P2 | 2 | Open |
| M-09 | Doc sprawl reduction (1,813 → ~300 canonical docs) | P2 | 2 | Open |
| M-10 | Prune stale remote branches | P3 | 3 | Open |
| M-11 | Merge `feature/harness-finalization-2026-06-20` → `main` | P3 | 3 | Open |
| M-12 | Wire `auto_clean` + `auto_heal` to CI schedule | P3 | 3 | Open |

---

## Phase 0 — Security & Stability (Do Now, No Blockers)

### M-01 · Rotate Leaked GitHub Token
**Threat level:** Critical  
**File:** `12_HANDOFFS/SESSION_2026-05-28_FINAL.md:84`  
**Pattern:** `ghp_REDACTED_ROTATED_2026-06-21...`

**Steps:**
1. Go to https://github.com/settings/tokens and revoke the token (by prefix `ghp_REDACTED_ROTATED_2026-06-21`)
2. Redact the line in the file: replace with `ghp_REDACTED_ROTATED_2026-06-21`
3. Check git history — if the token appears in a committed version, use `git filter-repo` or BFG to purge history
4. Commit the redaction

**Acceptance:** Token revoked in GitHub; `git grep "ghp_REDACTED_ROTATED_2026-06-21"` returns no matches in any tracked file.

---

### M-02 · Fix Syntax Error in `rudalo_migration_audit.py`
**File:** `scripts/rudalo_migration_audit.py:339`  
**Error:** F-string backslash (invalid in Python <3.12)

**Fix pattern:**
```python
# BAD (line 339 area):
f"some string with \n inside f-string"

# GOOD — extract the escape into a variable:
newline = "\n"
f"some string with {newline} inside f-string"
# OR use a regular string if the f is unnecessary
```

**Acceptance:** `python -m py_compile scripts/rudalo_migration_audit.py` exits 0.

---

## Phase 1 — Infrastructure Integrity

### M-03 · Push `main` to Origin
**Gap:** Local `main` has 13 commits not present on `origin/main`.

```bash
git checkout main
git push origin main
git log --oneline origin/main..main  # must return empty
```

**Acceptance:** `git log origin/main..main` is empty; GitHub shows main at `64943fa`.

---

### M-04 · Fix Pytest Environment (hydra-core / antlr4 Mismatch)
**Error:** `antlr4` runtime expects ATN version 4; `hydra-core==1.3.2` was compiled against version 3.

**Root cause:** `hydra-core` and `antlr4-python3-runtime` version mismatch in the global Python 3.11 env.

**Resolution options (in priority order):**
1. **Preferred — use a venv:**
   ```bash
   python -m venv .venv
   .venv/Scripts/activate
   pip install -r requirements.txt
   pytest
   ```
2. **Patch global env:**
   ```bash
   pip install "antlr4-python3-runtime==4.13.2" "hydra-core==1.3.2"
   # hydra-core 1.3.2 requires antlr4==4.9.3 — if conflict persists:
   pip install "hydra-core>=1.3.2" --upgrade
   ```
3. **Uninstall hydra-core if unused:**
   ```bash
   pip show hydra-core  # check if actually imported by any harness module
   pip uninstall hydra-core -y
   ```

**Acceptance:** `python -m pytest tests/test_auto_clean.py -v` shows 24 passed.

---

### M-05 · Update `ARTIFACT_MANIFEST.json` Stale Entry
**File:** `ARTIFACT_MANIFEST.json`  
**Issue:** `adapters.claude` points to `.claude/CLAUDE.md` which does not exist on disk.

**Fix:** Update the `adapters.claude` key to the correct path (`CLAUDE.md` at repo root) or remove it.

```bash
# Verify correct path:
ls CLAUDE.md  # exists at root
# Then edit ARTIFACT_MANIFEST.json adapters.claude → "CLAUDE.md"
```

**Acceptance:** `python -c "import json,pathlib; m=json.load(open('ARTIFACT_MANIFEST.json')); [pathlib.Path(v).exists() or exit(1) for v in m.get('adapters',{}).values() if not v.startswith('http')]"` exits 0.

---

### M-06 · Delete Stale Local Branches
**Branches to delete:**
- `CC-Desk/bold-mayer-90b4d5` — worktree branch, merged into main, no longer active
- `feat/harness-v2-30day-remediation-complete` — merged (confirmed)
- `feat/review-intake-loop-metrics` — merged (confirmed)

```bash
git branch -d CC-Desk/bold-mayer-90b4d5
git branch -d feat/harness-v2-30day-remediation-complete
git branch -d feat/review-intake-loop-metrics
```

**Acceptance:** `git branch` shows ≤5 local branches.

---

## Phase 2 — Coverage & Quality

### M-07 · Runtime Module Test Coverage Sprint
**Gap:** 30 source files in `02_RUNTIME/` have zero test coverage.

**Priority order (highest blast radius first):**

| Module | Risk if untested |
|--------|-----------------|
| `orchestrator.py` | All agent dispatch flows |
| `budget.py` | Token governance — billing leaks |
| `db.py` | Data persistence — silent corruption |
| `queue.py` | Job ordering — phantom work |
| `server.py` | API surface — undetected regressions |
| `task_graph.py` | DAG execution — deadlock risk |
| `enforcer.py` | Policy enforcement — security gaps |
| `guard.py` | Gate logic — bypass risk |
| `handlers.py` | Event routing — silent drops |
| `permission.py` | Access control — privilege escalation |
| `self_heal.py` | Recovery logic — compounding failures |
| `store.py` | State persistence |
| `verifier.py` | Validation — false positives |
| `main.py` | Entry point — startup regressions |
| `ollama_adapter.py` | Local model routing |

**Convention:** one `tests/test_<module>.py` per module. Each file must have ≥5 test cases (happy path, error path, boundary, fail-open, integration smoke).

**Target:** `pytest --cov=02_RUNTIME --cov-report=term-missing` shows ≥80% line coverage for all 30 modules.

---

### M-08 · Scripts Test Coverage Sprint
**Gap:** 139 scripts in `scripts/` have no `test_` counterpart.  
**Note:** `pytest.ini` intentionally scopes coverage to `02_RUNTIME` — scripts coverage must be tracked separately.

**Approach:**
1. Triage the 139 into three buckets:
   - **Test-worthy** (has logic, called programmatically): write `tests/scripts/test_<name>.py`
   - **One-off utilities** (run once, no return value): add a `--self-test` flag and smoke in CI
   - **Dead code** (never called, no callers in codebase): open a bead to delete

2. Target 60% coverage for test-worthy scripts (≈83 scripts) in this sprint.

**Quick wins (already have test patterns to copy):**
- `auto_clean.py` → `test_auto_clean.py` (done)
- `auto_heal.py` → `test_auto_heal.py` (done)
- `harness_swot.py` → `test_harness_swot.py` (done)

---

### M-09 · Doc Sprawl Reduction
**Current:** 1,813 `.md` files  
**Target:** ≤300 canonical docs  
**Key offenders:**
- 41 copies of `README.md` across subdirs
- 9 overlapping observability docs (`PDR_CHROMATIC_HARNESS_OBSERVABILITY*.md`, `OBSERVABILITY_*.md`)
- 4 copies of `DEPLOYMENT_GUIDE.md`
- 7 copies of `ARCHITECTURE.md`
- `02_DOCS/` folder has only 1 file despite being the designated docs folder

**Approach:**
1. Establish canonical locations:
   - Architecture → `02_DOCS/ARCHITECTURE.md`
   - Observability → `02_DOCS/OBSERVABILITY.md`
   - Deployment → `DEPLOYMENT_GUIDE.md` (root, single copy)
2. Convert subdirectory READMEs to stubs that link to canonical
3. Archive `HARNESS_V2_30DAY_REMEDIATION_COMPLETE.md`, `OPTION_C_COMPLETE.md` to `12_HANDOFFS/archive/`
4. Delete duplicate observability docs; keep only the most recent

**Acceptance:** `(Get-ChildItem -Recurse -Filter "*.md" | Measure-Object).Count -le 300`

---

## Phase 3 — Automation & Merge

### M-10 · Prune Stale Remote Branches
**Branches to delete from origin:**
- `origin/fix/junction-path-correction-2026-06-20` — fix merged
- `origin/session/chromatic-harness-v2-initial` — bootstrapped, superseded
- `origin/feat/command-center-p1-p2` — verify merged then delete
- `origin/docs/harness-v2-assessment-synthesis` — local ahead 3, decide: merge or delete

```bash
# Verify each is merged before deleting:
git log origin/main..origin/fix/junction-path-correction-2026-06-20 --oneline
# If empty = merged, safe to delete:
git push origin --delete fix/junction-path-correction-2026-06-20
```

**Acceptance:** `git branch -r` shows ≤4 remote branches (main, HEAD, __dolt_remote_info__, feature/harness-finalization-2026-06-20).

---

### M-11 · Merge `feature/harness-finalization-2026-06-20` → `main`
**Current state:** Feature branch is 1 commit ahead of origin counterpart (the cleanup commit we just added).

**Steps:**
1. Complete all Phase 0–1 missions first (especially M-03 push main)
2. Create PR: `gh pr create --title "feat: harness finalization 2026-06-20" --base main`
3. Ensure CI passes
4. Merge via squash or standard merge

**Acceptance:** `git log main..feature/harness-finalization-2026-06-20` is empty; GitHub PR shows merged.

---

### M-12 · Wire `auto_clean` + `auto_heal` to CI Schedule
**Goal:** Run cleanup and healing on every push + nightly, not manually.

**Add to `.github/workflows/harness-daily-audit.yml`:**
```yaml
- name: Auto Clean (dry-run)
  run: python scripts/auto_clean.py --dry-run

- name: Auto Heal (check-only)
  run: python scripts/auto_heal.py --check-only
```

**For cron runs, add `--force` variant:**
```yaml
- name: Auto Clean (apply)
  if: github.event_name == 'schedule'
  run: python scripts/auto_clean.py --force
```

**Acceptance:** `harness-daily-audit.yml` CI run shows both steps green.

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Pytest passing | 0 (env broken) | ≥56 (all new tests) |
| Script test coverage | 59% (97/236) | 75% |
| Runtime module coverage | ~80% (97 of 127) | ≥90% |
| Tracked .pyc files | 0 ✓ | 0 |
| Active worktrees | 1 (main) ✓ | 1 |
| Local branches | 8 | ≤5 |
| Remote branches | 9 | ≤4 |
| .md file count | 1,813 | ≤300 |
| `main` sync to origin | 13 behind | 0 |
| Known security issues | 1 (token) | 0 |
| Syntax errors | 1 | 0 |

---

## Contacts & Escalation

| Role | Scope |
|------|-------|
| Session owner | All missions |
| `auto_heal.py` | Automated healing — M-04 failure fallback |
| `harness_swot.py` | Metric re-run after each phase completes |
