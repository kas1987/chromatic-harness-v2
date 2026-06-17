# Session Retrospective — Harness Cleanup + LFS/Log Hygiene

**Date:** 2026-06-16
**PRs:** #266 (open — `chore/harness-cleanup-retention`)
**Scope:** Reconcile a large uncommitted cleanup, fix the GitHub large-file push
warning, and add prevention controls.

## What shipped (on PR #266)
- **Log-retention sweep** — `log_retention.py` removed 250 stale dated per-run
  snapshots (`token_governance/`, `unified_guard/`); reconciled the concurrent
  automation's CI policy-matrix + PDR work into one coherent commit instead of
  fighting it.
- **Large-file fix** — untracked the 59 MB `WORKFLOW_RUN_LOG.jsonl` and an
  `agentops-events.jsonl` (both already `.gitignore`d but committed before the
  rule existed).
- **Prevention** — `large_file_gate.py` (blocks ≥45 MB blobs and any
  staged/tracked file matching `.gitignore`), wired into `git_hooks/pre-commit`
  and the blocking CI governance gate; `.large-file-allowlist`; policy doc.
- **Rotation** — `log_retention.rotate_jsonl()` (line/byte cap + archive) wired
  into the token-governance writer so the protected append-only audit log
  self-caps going forward.
- **Merge** — resolved an add/add conflict with `main` on
  `auto-update-branches.yml` (kept `main`'s app-id fix + the branch's
  fail-on-error feature).
- Tests: 20 passing (gate + retention/rotation).

## Learnings

### 1. "Automation editing the repo live" was concurrent Claude sessions, not a cron
Disabling the `InReviewWatcher` scheduled task did **not** stop commits landing
on the branch. Root cause: multiple `claude.exe` sessions on the same checkout,
one running its own wrap-up flow. The scheduled `.ps1` tasks don't commit at all.
**Action:** when the tree changes under you, check running `claude.exe` + `git
reflog` (commits use a shared local identity, so author won't distinguish them) —
not just `schtasks`.

### 2. `git check-ignore` skips tracked files unless you pass `--no-index`
The first scan for tracked-but-ignored files came back empty and missed the
59 MB log. `--no-index` is required to catch files that were committed before an
ignore rule was added.
**Action:** audit with `git ls-files | git check-ignore --no-index --stdin`.

### 3. Ship tooling, not data churn
Committing the *rotated content* of the audit log put audit JSON into the PR diff
and hard-blocked the merge-confidence privacy gate. The rotation is wired into
the writer, so the data shrinks on the next run regardless.
**Action:** for generated/telemetry files, land the mechanism and revert the
file to base; never commit the regenerated payload.

### 4. A "9.5 MB large file" can be a submodule
`roach-pi` showed a large working-tree size but is a submodule gitlink — git only
tracks a 40-char pointer. `du` of the working tree ≠ tracked blob size.
**Action:** confirm with `git ls-files` / `git submodule status` before acting.

### 5. Stacked cleanup can't branch cleanly off main
The cleanup edits sat on top of the feature commits (10 overlapping files), so a
strict "fresh branch off main" was infeasible. Branched off the feature tip; the
cleanup commit stays reviewable in isolation.

### 6. `subprocess(text=True)` mangles UTF-8 on Windows
`git show` via `text=True` decoded em-dashes as cp1252 mojibake. Capture bytes
and `.decode("utf-8")` when reconstructing files.

## KPI snapshot
| Metric | Before | After |
| --- | --- | --- |
| Largest tracked file | 59 MB (ignored, tracked) | untracked |
| Tracked audit log cap | none (unbounded) | byte-capped via writer |
| Large-file regression guard | none | pre-commit + blocking CI |
| Stale per-run snapshots | 250 | 0 |

## Follow-up
- **PR #266 is BLOCKED by the merge-confidence gate (human-gated):** 4 unresolved
  review threads, 1 conflicting sibling PR on base, and compliance-doc content
  needing human ack. The hard-block from the audit-log diff was cleared (learning
  #3). Resolve reviews + sibling PR, then ack.
- **T4 (needs approval):** purge the 59 MB blob from history — runbook at
  `~/harness_cleanup_archive/HISTORY_PURGE_RUNBOOK.md`.
- Re-enable `InReviewWatcher` after merge:
  `schtasks /change /tn "\ChromaticHarness\InReviewWatcher" /enable`.
- Coordinate/close the concurrent Claude sessions before further branch work.
- Deferred beads: `zdnm`, `ckqr`, `gh4a`, `28iz`.
