# PDR — Harness V2 Remediation & Hardening

**Status:** active · **Date:** 2026-06-21 · **Branch:** `feature/harness-finalization-2026-06-20`

> Resolve the twelve open findings from the 2026-06-21 SWOT audit: one security threat, two stability defects, six coverage gaps, and three hygiene/sync issues — without introducing new infra or changing any public API surface.

---

## 1. Problem

The 2026-06-21 automated audit (`scripts/harness_swot.py`, 15-agent workflow) surfaced:

- **Security (P0):** A literal GitHub PAT (`ghp_REDACTED_ROTATED_2026-06-21...`) is present in a tracked handoff document. Token is potentially still valid.
- **Stability (P0):** `scripts/rudalo_migration_audit.py:339` contains an f-string backslash, causing a `SyntaxError` on Python <3.12. The file fails `py_compile`.
- **Infrastructure (P1):** Local `main` is 13 commits ahead of `origin/main` — the primary sync target for the GitHub repo is stale. `pytest` is fully broken due to a `hydra-core==1.3.2` / `antlr4` ATN version mismatch.
- **Coverage (P2):** 30 of 127 `02_RUNTIME/` source files have zero test coverage. 139 of 236 scripts lack test pairs. pytest is configured correctly but can't run.
- **Hygiene (P2-P3):** 1,813 `.md` files (target ≤300). 3 stale local branches. 7 stale remote branches. `ARTIFACT_MANIFEST.json` references a non-existent adapter path.

---

## 2. Reuse Survey

| Asset | Location | Role |
|-------|----------|------|
| `auto_clean.py` | `scripts/auto_clean.py` | Already written — wire to CI, extend for log retention |
| `auto_heal.py` | `scripts/auto_heal.py` | Already written — extend to fix gitignore, __init__.py |
| `harness_swot.py` | `scripts/harness_swot.py` | SWOT baseline — re-run after each phase to track progress |
| `harness_health_check.py` | `scripts/harness_health_check.py` | Existing health checker — extend, not replace |
| `harness-daily-audit.yml` | `.github/workflows/harness-daily-audit.yml` | CI hook to wire auto_clean + auto_heal into schedule |
| `pytest.ini` | root | Already correctly configured: `pythonpath=02_RUNTIME`, `testpaths=tests` |
| `requirements.txt` | root | Extend to pin `antlr4-python3-runtime==4.9.3` and `hydra-core==1.3.2` |
| `ARTIFACT_MANIFEST.json` | root | Extend with 3 new scripts; fix stale adapter path |
| `_PDR_TEMPLATE.md` | `08_PDRS/` | This PDR follows that template |

**Out of scope for reuse (do not rebuild):**
- `collision_guard.py`, `collision_check.py` — existing collision layer is adequate; do not duplicate
- `.github/workflows/ci.yml` — full CI workflow; only extend `harness-daily-audit.yml`

---

## 3. Non-Goals

- Will NOT migrate the Python environment to a container or Docker
- Will NOT change the public API of `02_RUNTIME/orchestrator.py` or any runtime module
- Will NOT restructure the top-level directory hierarchy (numbered folders stay)
- Will NOT touch the Dolt/beads embedded database or its storage format
- Will NOT add new CI providers or notification systems
- Will NOT address the `docs/multi-drive-rollout-guide` or `feat/u8uj-4-router-orchestrator-split` branches (not merged — require separate review)
- Will NOT archive or delete any `.md` file without confirming it is superseded

---

## 4. Design

### 4.1 Security Remediation (M-01)

Token redaction is a two-step operation: revoke via GitHub web UI, then overwrite the file. Git history must be inspected — if `ghp_REDACTED_ROTATED_2026-06-21...` appears in any committed blob, `git filter-repo --replace-text` must be run and a force-push to all branches executed.

```
Detection command:
  git log --all -p | grep "ghp_REDACTED_ROTATED_2026-06-21"

If found in history:
  pip install git-filter-repo
  printf "ghp_REDACTED_ROTATED_2026-06-21...**REDACTED**\n" > /tmp/replacements.txt
  git filter-repo --replace-text /tmp/replacements.txt
  git push --force-with-lease origin --all
```

### 4.2 Syntax Fix (M-02)

Single-line fix. Extract the escape sequence to a variable before the f-string. The pattern `f"...\n..."` is valid in Python 3.12+ only. The harness targets Python 3.11.9.

```python
# Line 339 area of scripts/rudalo_migration_audit.py
# BEFORE:
msg = f"Migration failed:\n{detail}"
# AFTER:
_nl = "\n"
msg = f"Migration failed:{_nl}{detail}"
```

### 4.3 Pytest Environment Fix (M-04)

The `hydra-core==1.3.2` package uses `antlr4` runtime internally. It was compiled against ATN version 3 but the installed `antlr4-python3-runtime` exposes ATN version 4. Resolution: either downgrade antlr4 to `4.9.3` (which hydra-core 1.3.2 targets) or remove hydra-core if it is unused by harness modules.

Data contract — `requirements.txt` pin:
```
antlr4-python3-runtime==4.9.3  # required by hydra-core==1.3.2
hydra-core==1.3.2
```

If hydra-core is unused (grep check): `pip uninstall hydra-core antlr4-python3-runtime` and remove from requirements.txt.

### 4.4 Test Coverage (M-07, M-08)

Each new test file follows the pattern established by `test_auto_clean.py`:
- Import the module fresh via `importlib.util.spec_from_file_location` to avoid global state
- Override `HARNESS_ROOT` / path constants with `tmp_path`
- At minimum: happy path, error path, boundary condition, fail-open, smoke integration

New test files land in `tests/` (already in `testpaths`). Runtime coverage is tracked by `pytest --cov=02_RUNTIME`.

### 4.5 Doc Sprawl (M-09)

Canonical doc map:

```
02_DOCS/ARCHITECTURE.md          ← absorbs 7 ARCHITECTURE.md copies
02_DOCS/OBSERVABILITY.md         ← absorbs 9 observability docs
DEPLOYMENT_GUIDE.md (root)       ← absorbs 4 DEPLOYMENT_GUIDE.md copies
<subdir>/README.md               ← stub: "See docs/..." link only
12_HANDOFFS/archive/             ← milestone completion docs (OPTION_C_COMPLETE, HARNESS_V2_30DAY_...)
```

Script: `scripts/doc_consolidator.py` (to be written in M-09) will:
1. Find all duplicate-named `.md` files
2. Diff content; if identical → delete duplicates, keep canonical
3. If diverged → open a bead for manual review
4. Convert subdirectory README to stub

---

## 5. Integration / Actuation Edge ⚠️ MANDATORY

**What runtime path calls this?**

- `auto_clean.py` and `auto_heal.py` are called by `.github/workflows/harness-daily-audit.yml` on `schedule` (nightly) and on every push to `main`. They are also available as manual scripts.
- `harness_swot.py` is called manually after each phase completes to update `05_REPORTS/HARNESS_SWOT_REPORT.md`.
- The pytest fix (M-04) activates all 56 new tests on every `pytest` invocation and every CI run via `ci.yml`.

**How will we PROVE it is live?**

| Mission | Live Proof |
|---------|-----------|
| M-01 (token) | `git grep "ghp_REDACTED_ROTATED_2026-06-21"` returns nothing in tracked files AND GitHub revocation confirms token inactive |
| M-02 (syntax) | `python -m py_compile scripts/rudalo_migration_audit.py` exits 0; CI `validate-command-prompt-system.yml` passes |
| M-03 (push main) | `git log origin/main..main` is empty; GitHub UI shows `main` at `64943fa` |
| M-04 (pytest) | `pytest tests/test_auto_clean.py -v` shows "24 passed"; `pytest tests/test_auto_heal.py -v` shows "25 passed" |
| M-07 (runtime coverage) | `pytest --cov=02_RUNTIME --cov-report=term-missing` shows ≥80% for all 30 previously-uncovered modules |
| M-12 (CI wire) | GitHub Actions log for `harness-daily-audit.yml` shows "Auto Clean" and "Auto Heal" steps green |

---

## 6. Lean Impact ⚠️ MANDATORY

| Question | Answer |
|----------|--------|
| Boot tax? | None — `auto_clean.py`, `auto_heal.py`, `harness_swot.py` are invoked explicitly (CLI or CI job), never on startup |
| Always-on vs event-driven? | Event-driven: CI schedule trigger (nightly) + push to main — not a poller |
| On-demand vs always-injected? | On-demand only; no import at session startup |
| Swappable producer? | Yes — `auto_heal.py` delegates health check to `harness_health_check.py`; swap health backend without touching heal logic |
| Token audit delta | Not applicable — no changes to `02_RUNTIME/` hot path; only new scripts and test files added |

---

## 7. Decomposition

| Bead | Artifact | Mission | Depends on |
|------|----------|---------|------------|
| **B1** | This PDR | — | — |
| **B2** ★ | Revoke token + redact `SESSION_2026-05-28_FINAL.md` | M-01 | B1 |
| **B3** | Fix `rudalo_migration_audit.py:339` | M-02 | B1 |
| **B4** | `git push origin main` | M-03 | B2, B3 |
| **B5** | Fix pytest env (antlr4 pin or hydra-core removal) | M-04 | B4 |
| **B6** | Fix `ARTIFACT_MANIFEST.json` adapter path | M-05 | B4 |
| **B7** | Delete 3 stale local branches | M-06 | B4 |
| **B8** | `tests/test_orchestrator.py` | M-07 | B5 |
| **B9** | `tests/test_budget.py` | M-07 | B5 |
| **B10** | `tests/test_db.py` | M-07 | B5 |
| **B11** | `tests/test_queue.py` | M-07 | B5 |
| **B12** | `tests/test_server.py` + `test_main.py` | M-07 | B5 |
| **B13** | `tests/test_task_graph.py` + `test_enforcer.py` | M-07 | B5 |
| **B14** | `tests/test_guard.py` + `test_permission.py` + `test_verifier.py` | M-07 | B5 |
| **B15** | `tests/test_self_heal.py` + `test_store.py` + `test_handlers.py` | M-07 | B5 |
| **B16** | `scripts/doc_consolidator.py` | M-09 | B6 |
| **B17** | Doc consolidation run — reduce .md count to ≤300 | M-09 | B16 |
| **B18** | Prune stale remote branches | M-10 | B4 |
| **B19** | Wire `auto_clean`/`auto_heal` to `harness-daily-audit.yml` | M-12 | B5 |
| **B20** | PR: merge `feature/harness-finalization-2026-06-20` → `main` | M-11 | B8-B19 |

_★ B2 is highest-ROI first step: token revocation prevents any further exposure during the rest of the sprint._

---

## 8. Tests & Hardening

- **Unit:** `pytest tests/test_auto_clean.py tests/test_auto_heal.py tests/test_harness_swot.py` — 56 tests, must be green before B20
- **Runtime coverage:** `pytest --cov=02_RUNTIME --cov-report=term-missing` — ≥80% for all targeted modules
- **Fail-open:** `auto_heal.py` exits 1 on unfixable issues but never raises uncaught exceptions — harness continues regardless
- **Security:** `scripts/scan_for_secrets.py` must pass with 0 hits after M-01 completes; `redact_secrets.py` available as fallback
- **Staleness guard:** `harness_swot.py` re-run after each phase — SWOT report timestamp must be ≤1 day old in CI
- **Doc consolidation guard:** `doc_consolidator.py` must not delete any `.md` that is the only copy — always keeps canonical

---

## 9. Definition of Done

- [ ] `git grep "ghp_REDACTED_ROTATED_2026-06-21"` returns empty in all tracked files (M-01)
- [ ] `python -m py_compile scripts/rudalo_migration_audit.py` exits 0 (M-02)
- [ ] `git log origin/main..main` is empty (M-03)
- [ ] `pytest tests/test_auto_clean.py tests/test_auto_heal.py` shows 49 passed (M-04)
- [ ] `ARTIFACT_MANIFEST.json` adapter paths all resolve on disk (M-05)
- [ ] `git branch` shows ≤5 local branches (M-06)
- [ ] `pytest --cov=02_RUNTIME` shows ≥80% line coverage for all 30 target modules (M-07)
- [ ] `(Get-ChildItem -Recurse -Filter "*.md").Count -le 300` (M-09)
- [ ] `harness-daily-audit.yml` CI run shows auto_clean + auto_heal steps green (M-12)
- [ ] `harness_swot.py` re-run shows 0 threats (token resolved, syntax fixed) (all)
- [ ] PR merged, feature branch deleted (M-11)
- [ ] `bd close <epic-id>` called

---

## 10. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Token already used to clone/exfiltrate | Low | Revoke immediately; token was in handoff doc not in `.env` or CI secrets |
| `git filter-repo` rewrites history, breaks collaborator checkouts | Medium | Only needed if token appears in git history; coordinate with kas1987 before force-push |
| hydra-core uninstall breaks a hidden import | Low | `grep -r "hydra" 02_RUNTIME/ scripts/` before removing; if found, pin antlr4 instead |
| Doc consolidation deletes diverged content | Medium | `doc_consolidator.py` opens a bead for any diverged file — no silent deletes |
| Runtime coverage tests reveal actual bugs | Medium-High | Stop-and-fix policy: any failing test in B8-B15 blocks B20 until resolved |
| Large-scale `.md` deletion breaks relative links | Medium | `scripts/harness_health_check.py` or `linkchecker` run post-consolidation |

---

## 11. Rollback

- **M-01 (token):** Irreversible by design — revocation is intentional. Redaction in file is a one-line change; revert with `git revert` if needed.
- **M-02 (syntax fix):** `git revert <commit>` restores the original (broken) file.
- **M-04 (pytest env):** `pip install antlr4-python3-runtime==<old-version>` or restore from `pip freeze` snapshot taken before the fix.
- **M-09 (doc consolidation):** All deleted files are archived to `12_HANDOFFS/archive/doc-consolidation-2026-06-21/` before deletion. Restore by copying back.
- **M-12 (CI wiring):** Remove the two added steps from `harness-daily-audit.yml` and revert via PR.
