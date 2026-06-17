# SWOT — Governance & Guard cluster
*Audit date: 2026-06-16 | Auditor: automated SWOT agent*

---

## Folder inventory

| Folder | Files | Total size | Newest mtime | has latest.json | Schema summary | Fresh / Stale |
|--------|------:|------------|--------------|:---------------:|----------------|:-------------:|
| `unified_guard` | 5,965 | 34.12 MB | 2026-06-16 11:35 | Yes | Per-run receipt: `ok`, `timestamp`, `surface`, `invoked_by`, `codegraph_status`, nested `steps[]` (exit codes + stdout/stderr tails) | **Fresh** (active today) |
| `governance_intelligence` | 45 | 1.07 MB | 2026-06-04 17:53 | Yes | Multi-source telemetry roll-up: event counts, canonical-field coverage %, provider/model rollup, schema drift analysis, `recommendations[]` | Stale (12 days) |
| `governance_review` | 1 | ~0.01 MB | 2026-06-01 08:27 | No — only `.gitkeep` | Intended: deterministic governance gate writing `latest.json` + timestamped copy; script exists but has never produced output in this dir | **Dead / never run** |
| `drift` | 5 | 0.01 MB | 2026-06-03 21:14 | Yes | Repo-structure drift vs baseline snapshot: `audit.current_entries`, `added_unexpected[]`, `removed[]`, `score`, `trend`, `recommendations[]` | Semi-stale (13 days) |
| `harness_health` | 2 | 0.01 MB | 2026-06-04 17:54 | Yes | Composite health dashboard: 18 named checks (pass/warn/fail), `readiness_score`, coverage metrics for provider/model/cost/latency, budget channel breakdown | Stale (12 days) |
| `claim_guard` | 2 | ~0 MB | 2026-06-01 10:54 | No — only `.gitignore` + `.gitkeep` | Stub folder; no data produced | **Empty stub** |

**Cluster totals: 6,021 files, 35.23 MB**

---

## Strengths

1. **`unified_guard` is genuinely active.** Running every session (via `session_unified_guard.py` called from hooks), producing a consistent, machine-readable JSON receipt with named `steps[]`, exit codes, and stdout/stderr tails. `latest.json` is consumed by `harness_health_snapshot.py` and `harness_kpi_console.py`, so the data has real downstream consumers.

2. **Strong schema in `harness_health`.** The 18-check dashboard (`latest.json`) covers cross-system signals (token governance, pre-session, codegraph, budget channels) in a single structured document with numeric `readiness_score`, making it easy to trend over time even though only one timestamped snapshot exists.

3. **`drift` is purposeful and actionable.** Has a `baseline.json` (55-entry expected structure snapshot), a `history.jsonl` (4-entry append log), and `recommendations[]` in every run output. The score+trend pattern (`score: 32, trend: worsening`) is exactly what a governance gate should surface. Correctly flags a `CUserskas41AppDataLocalTemppr_checks.json` file leaked into the repo root.

4. **`governance_intelligence` history depth.** The `history.jsonl` covers 35 runs with per-run canonical-field-coverage analytics (confidence_score, cost_usd, latency_ms), enabling trend analysis over the 2026-05-30 burst period. The script (`llm_governance_intelligence.py`) also enforces a `max_files=14` retention cap on routing logs it reads — good discipline at the source.

5. **`latest.json` + timestamped-copy dual-write pattern** is consistent across `unified_guard`, `governance_intelligence`, `drift`, and `harness_health`. This makes "what happened last run" trivially accessible without directory scans.

---

## Weaknesses

1. **`unified_guard` has unbounded file growth with zero rotation.** The script (`session_unified_guard.py`) calls `_write_receipt()` which writes `session_guard_<stamp>.json` + `latest.json` every run — no prune, no max-files, no TTL. With ~800–1000 files per active day, the folder is at 5,965 files / 34 MB after only 11 active days. At current pace this reaches 50,000+ files within 60 days, which will cause filesystem performance degradation (especially on Windows NTFS with per-directory entry limits) and bloat git operations if ever accidentally staged.

2. **`governance_intelligence` is 12 days stale and its `latest.json` is not the newest file.** The `canary_snapshot_latest.json` (2026-06-04) is newer than `latest.json` (2026-05-30), meaning harness_health reads an outdated telemetry picture. More critically: the 45 timestamped run files cluster entirely within a 48-hour window (all 2026-05-30) and have not been produced since, suggesting the `llm_governance_intelligence.py` pipeline is broken or no longer wired to a hook.

3. **`governance_review` and `claim_guard` are empty stubs.** `governance_review` has a script that is well-written and produces a timestamped artifact, but has never been executed against this repo (only `.gitkeep` exists; no `latest.json`). `claim_guard` has only `.gitignore` + `.gitkeep`. Both consume directory entries and create false confidence that governance coverage exists.

4. **`harness_health` has only one snapshot file** (`latest.json` + `latest.md`); no timestamped history, no `history.jsonl`. The `readiness_score: 24` (red status, 13/18 checks pass, 3 fail) was recorded 12 days ago and the state may have changed. Without a history file, trend analysis is impossible.

5. **Schema fragmentation in `governance_intelligence`.** The canonical coverage data shows `cost_usd` and `latency_ms` coverage at only 33% across 6,318 logged events, and 73% of ledger events are `unknown` provider. The intelligence output documents this but the root cause (emitters not populating required fields) is unaddressed.

6. **`drift` baseline is stale relative to current repo structure.** The baseline encodes 55 top-level entries but `latest.json` reports 58 current and 46 `added_unexpected` — meaning the baseline was snapped during an earlier repo state and has not been re-anchored after intentional additions. This produces noisy recommendations that mix real drift with approved structural changes.

---

## Opportunities

1. **Add a `--prune-older-than-days N` flag to `session_unified_guard.py`** and call it on every run. Even a 7-day retention window would reduce `unified_guard` from 5,965 → ~800 files permanently. The `latest.json` pointer preserves full access to the most recent run regardless.

2. **Re-anchor `drift/baseline.json`** after confirming current approved top-level structure. Once anchored, the drift check becomes a meaningful gate (right now a score of 32 is noise). Wire the drift check into the pre-push or daily audit pipeline and surface it on the harness health dashboard.

3. **Wire `governance_review.py` to a hook or scheduled job.** The script is production-quality; it just has never been called. Running it once per session closeout (or weekly) would fill the `governance_review/` folder and give the harness a holistic governance gate output alongside `unified_guard`.

4. **Emit timestamped snapshots from `harness_health_snapshot.py`** alongside `latest.json`. A rolling `harness_health_history.jsonl` append (one line per run, summary fields only) would enable trend charting of `readiness_score` over time at near-zero storage cost.

5. **Define `claim_guard`'s purpose or delete the folder.** If claim-guard logic will be implemented (e.g., validating bead claims against actual work), create a stub schema + script now. If it is deferred indefinitely, remove the folder and its `.gitignore` to reduce dead surface area.

6. **Consolidate `governance_intelligence` runs** — the 45 same-day files could be replaced with a single `history.jsonl` appended per run (as with `drift`), reducing file count while keeping history. The current dated-file pattern generates significant NTFS overhead when runs are frequent.

---

## Threats

1. **NTFS directory entry saturation in `unified_guard`.** At 5,965 files today and ~900 files/day on active days, the folder will hit tens of thousands of files in weeks. Windows Explorer, `Get-ChildItem`, and git-status all degrade non-linearly past ~10,000 files in a single directory. No mitigation is currently in place.

2. **`harness_health` reads a stale `governance_intelligence/latest.json`.** The health snapshot's `coverage_provider_model` and `coverage_task_exec` checks warn based on data that is 12+ days old. A stale-input check would prevent false confidence in the health score.

3. **Drift check "worsening" trend with no automated enforcement.** The drift score has been 32 and "worsening" since at least 2026-06-04 with no remediation loop. Without a gate that fails PRs or sessions when drift score drops below a threshold, this signal is advisory-only and will decay toward being ignored.

4. **`governance_review` never being executed means its stub latency is invisible.** Other sub-systems (e.g., `session_closeout.py`) reference `governance_review.summarize()` as a fail-open call — if the module has a bug or import failure, it silently returns an empty dict, masking the problem.

5. **Secrets / ephemeral path contamination.** The `drift/latest.json` already flagged `CUserskas41AppDataLocalTemppr_checks.json` leaked into the repo root. Unchecked drift enables similar artifacts to accumulate without automated cleanup. The `claim_guard/.gitignore` stub suggests awareness of this risk but provides no active protection.

---

## Cleanup Recommendations

### P0 — Do immediately (prevents runaway growth / data integrity issues)

**P0-A | `unified_guard`: Add file rotation (prune > 7 days)**
- **Action**: In `scripts/session_unified_guard.py`, after writing the new timestamped file, add a prune step: delete `session_guard_*.json` files older than 7 days. Implement as a `_prune_old_receipts(days=7)` helper called from `main()`.
- **Rationale**: 5,965 files / 34 MB today with no upper bound. At ~900 files/active day this is the highest-urgency storage issue in the cluster.
- **Folder**: `unified_guard`

**P0-B | `drift`: Re-anchor baseline.json to current approved structure**
- **Action**: Run `scripts/drift_check.py --rebaseline` (or equivalent) after confirming every `added_unexpected` entry in `latest.json` is intentional. Commit the new `baseline.json`. This immediately reduces noise recommendations from 18 → 0 and makes the drift gate meaningful.
- **Rationale**: A drift score of 32/100 ("worsening") against an outdated baseline is a false alarm that erodes trust in the governance signal.
- **Folder**: `drift`

### P1 — Do this sprint (fixes stale data / wasted surface area)

**P1-A | Wire `governance_review.py` to a hook**
- **Action**: Add `governance_review.py` to the session closeout hook sequence (after `unified_guard`). The script is production-quality and already has `ARTIFACT_DIR` set correctly; it just needs a caller.
- **Rationale**: `governance_review/` is a dead folder with a working script. Every session closeout without it is a missed governance checkpoint.
- **Folder**: `governance_review`

**P1-B | Add staleness check for `governance_intelligence/latest.json` in `harness_health_snapshot.py`**
- **Action**: Before reading `governance_intelligence/latest.json`, check its mtime. If older than 24h, mark the health check `warn`; if older than 72h, mark `fail`. Currently the health snapshot silently ingests 12-day-old coverage data.
- **Rationale**: `harness_health` is the harness's primary red/green indicator. Feeding it stale inputs produces misleading readiness scores.
- **Folders**: `harness_health`, `governance_intelligence`

**P1-C | Add timestamped append to `harness_health_snapshot.py`**
- **Action**: After writing `latest.json`, append a summary row (timestamp, readiness_score, pass/warn/fail counts) to `harness_health_history.jsonl`. No schema change needed to `latest.json`.
- **Rationale**: With only a single snapshot file, there is no way to trend readiness_score over time. A 100-byte JSONL append per run costs nothing.
- **Folder**: `harness_health`

**P1-D | Delete or define `claim_guard`**
- **Action**: If claim-guard validation is planned within 30 days, add a `claim_guard/README.md` + stub schema. If not, delete the folder and remove its `.gitignore` to eliminate dead surface area.
- **Rationale**: An empty stub that appears in directory listings creates false confidence and adds noise to audits.
- **Folder**: `claim_guard`

### P2 — Backlog (quality improvements, lower urgency)

**P2-A | Consolidate `governance_intelligence` to `history.jsonl` append model**
- **Action**: Modify `llm_governance_intelligence.py` to append a summary row to `history.jsonl` on each run rather than writing a new dated JSON file. Retain the `latest.json` full-output write. Delete the 45 existing dated files after migrating their data.
- **Rationale**: 45 files from a single 48-hour burst is unnecessary. The `history.jsonl` model (already used by `drift`) achieves the same history at 1 file.
- **Folder**: `governance_intelligence`

**P2-B | Add drift enforcement to pre-push or daily-audit gate**
- **Action**: Wire `drift/latest.json` score into `daily_harness_audit.py --strict`. If `score < 50` or `trend == "worsening"`, emit a warning (not hard fail initially). Escalate to fail after the baseline is re-anchored (see P0-B).
- **Rationale**: Drift is currently advisory-only. Without enforcement it will be ignored.
- **Folder**: `drift`

**P2-C | Re-activate `governance_intelligence` pipeline**
- **Action**: Investigate why `llm_governance_intelligence.py` stopped running after 2026-05-30. Check if it was removed from hook sequence or if a dependency changed (e.g., routing log format). Restore to daily or per-session cadence.
- **Rationale**: Provider/model/cost coverage tracking is valuable signal. 12 days of silence means it missed the model routing changes from 2026-06-05.
- **Folder**: `governance_intelligence`

---

## Cross-cluster notes

- **Token cluster overlap**: `unified_guard/latest.json` embeds the full `token_governance_closed_loop` stdout tail (6 KB+ of JSON as a string). This creates redundancy with `07_LOGS_AND_AUDIT/token_governance/latest.json`. Consider truncating `stdout_tail` to status fields only (ok, status, suggestions count) to keep guard receipts compact.

- **Session-lifecycle cluster overlap**: `harness_health_snapshot.py` explicitly reads `pre_session/latest.json` as an input (`pre_session_fresh` check). Any change to the `pre_session` schema will break the health snapshot silently (fail-open). A schema version field on both ends would prevent silent drift.

- **Intake/queue cluster overlap**: `governance_review.py` is referenced by `session_closeout.py` as a `summarize()` call-site. Because `governance_review/latest.json` has never been written, `session_closeout` may be logging empty/stub governance data into the closeout record without surfacing an error.

- **Security cluster overlap**: `drift` already detected a `CUserskas41AppDataLocalTemppr_checks.json` file in the repo root (a Windows temp path artifact). This pattern — temp files leaking into the working tree — should also be flagged by any security-sweep script. The security cluster audit should verify whether the `pr_checks.json` file has been cleaned up.

- **Learning cluster note**: `governance_intelligence` `recommendations[]` (e.g., "Improve telemetry: confidence_score coverage is 44%") are not being fed back into a learning or backlog system. If a learning cluster exists, a bridge from `governance_intelligence/latest.json#recommendations` → intake queue would automate schema-improvement tracking.
