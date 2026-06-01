# Session Retrospective — Governance Gates: Two Epics Shipped via Parallel Subagents

**Date:** 2026-06-01
**PRs merged:** #69, #70, #71, #72, #73 (+ earlier #66, #67)
**Epics closed:** `nzn0` CI & Quality Hardening (15/15), `v37g` Release & Ops Readiness (10/10)

## What shipped

Eight governance gates, each following one repeatable pattern (standalone script →
artifact under `07_LOGS_AND_AUDIT/` → `summarize()` → wired into closeout + pre-push →
test suite → bead checkboxes → epic-review reflects progress):

- **gh-57** `security_scan.py` — secret regex scan + `pip-audit` (scoped to requirements.txt) → fail on high-sev.
- **gh-60** `pr_size_gate.py` — diff metrics + protected-path detection + configurable warn/fail thresholds.
- **gh-58** (3 parallel subagents) `coverage_gate.py` + `docs_drift_gate.py` + `arch_compliance_gate.py`.
- **gh-61** `drift_gate.py` — tree audit, drift score, trend tracking, remediation recs.
- **gh-62** `release_readiness.py` — meta gate aggregating all sibling artifacts into one GO/NO-GO.

Both epics reached **SHIP** via `epic_review.py` (0/N → N/N as children landed), with the
summarized E2E review posted to the epic bead (Policy §5).

## Learnings

### 1. Parallel subagents work cleanly when they write DISJOINT files and do NO git ops
gh-58 (3 areas) and v37g (2 beads) were each fanned out to concurrent sonnet subagents.
The key constraint that made it conflict-free: each subagent created ONLY its own
`scripts/<gate>.py` + `tests/test_<gate>.py`, was forbidden from touching shared files
(`run-all-e2e.py`, `session_closeout.py`, `pyproject.toml`) and from committing. The parent
integrated the shared wiring in one commit. 6 files + 36 tests in ~100s for gh-58.
**Action:** For fan-out builds, give each agent a disjoint file set and reserve all shared-file edits + git for the orchestrator.

### 2. The auto-mode branch hazard recurred — and now reverts EDITS, not just branches
Twice this session a background auto-mode process (a) reverted my edits to `session_closeout.py`
and `run-all-e2e.py` *before* I could commit, and (b) switched my checkout to a pre-created
`skqu-governance-review` branch mid-operation, making correct work look lost (I was inspecting
the wrong branch's HEAD). The fix: `git rev-parse HEAD` vs `git rev-parse origin/<branch>` and
`git show <branch>:<file>` to inspect the RIGHT branch before concluding anything is missing.
**Action:** After any "my change vanished" surprise, FIRST run `git branch --show-current` — the churn may have moved you, not deleted your work. Commit edits to shared files immediately and re-verify on the named branch, not HEAD.

### 3. Meta-gates should aggregate artifacts, not re-run scans
`release_readiness.py` reads the other gates' `latest.json` artifacts rather than re-running
them — fast, and the artifact-per-gate convention made aggregation trivial. Every gate writing
`07_LOGS_AND_AUDIT/<area>/latest.json` + a `summarize()` is what let the meta-gate and the
closeout report compose without coupling.
**Action:** Standardize new gates on the artifact + `summarize()` contract; meta-views read artifacts.

### 4. A scanner that documents its own patterns must allowlist its fixtures
`security_scan.py` correctly flagged the sample secrets in its own test file (true positive).
Resolved with the standard `# pragma: allowlist secret` line convention, not by weakening
detection or skipping test dirs wholesale.
**Action:** Use line-level allowlist pragmas for known-safe fixtures; never blunt the detector.

### 5. Scope external scanners to the project, not the ambient environment
`pip-audit` on the ambient interpreter reported 72 CVEs (dev tooling); scoped to
`requirements.txt` it reported 0 (the meaningful signal). An unscoped scanner makes the gate
permanently red and useless.
**Action:** Scope dependency/security scanners to project manifests; ambient noise is not a gate signal.

## KPI snapshot
| Metric | Value |
|--------|-------|
| Epics shipped this session | 2 of 4 (nzn0, v37g) |
| Governance gates built | 8 (security, pr-size, coverage, docs-drift, arch, drift, release-readiness) |
| Eval gates passed | 25/25 across the two epics |
| New tests added | ~110 (gate suites) |
| PRs merged | 5 (#69–#73) |
| Closeout instrumentation keys | security, pr_risk, coverage, docs_drift, arch_compliance, drift, release_readiness, epic_reviews |

## Follow-up
- **Remaining epics:** `skqu` Governance & Review Layer (gh-59/63/64/65 — C3/C4, design-heavy), `ls80` Queue Infrastructure (gh-51).
- **Tech debt:** 7 stray `*-churn` stashes from auto-mode interference — safe to drop.
- **Next bead:** `bd ready` / start `ls80` (quick single-bead epic) before the C4 `skqu` work.
