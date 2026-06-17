# Harness & Repo Cleanup Plan — Chromatic Harness v2

**Date:** 2026-06-16 · **Scope:** `07_LOGS_AND_AUDIT/` (38 folders) + `08_PDRS/` lifecycle process
**Method:** 6 parallel SWOT agents (one per functional cluster) + orchestrator synthesis. Per-cluster
detail in the sibling `SWOT_0*.md` files. PDR-tracking deliverables in `08_PDRS/` (see §5).

---

## 1. Executive summary

`07_LOGS_AND_AUDIT/` holds **~12,400 files / ~281 MB**, but the overwhelming majority is
**unrotated append-log exhaust and phantom/stale data**, not actionable signal. Four folders
account for nearly all of it, and three of the largest files are non-actionable (dummy zeros,
an empty-state 85 MB dump, redundant per-run snapshots).

| Cluster (SWOT file) | Files | Size | Dominant problem |
|---|---|---|---|
| Governance/Guard (`SWOT_01`) | 6,021 | 35 MB | `unified_guard` ~900 files/day, no rotation; `governance_intelligence` 12d stale |
| Token/Budget (`SWOT_02`) | 5,773 | 70 MB | `token_governance` 5,742 redundant per-run files; 71% "unknown" token class; `command_matrix` broken |
| Intake/Triage (`SWOT_03`) | ~30 | ~86 MB | `staged_issues.jsonl` 85 MB but state empty; `intake_queue` 1317 lines/248 unique, 395 stuck "processing" |
| Session-lifecycle (`SWOT_04`) | 272 | 86 MB | `traces.jsonl` 40 MB of zero-value dummy rows; unrotated manifests; not gitignored |
| Security (`SWOT_05`) | 286 | 0.08 MB | dep-scan skipped in 282/283 scans yet `passed:true` — posture is partial, not green |
| Learning/Analytics (`SWOT_06`) | 45 | 4 MB | 9/11 folders stale 12–17d; demo/skeleton data; micro-folder sprawl |

**Bottom line:** the observability tree *looks* rich but a large fraction is bloat, stale, or
audit theater. Cleanup is high-leverage: a handful of P0 actions reclaim **~250 MB** and remove
the misleading-green signals that are corrupting governance decisions.

---

## 2. Cross-cutting patterns (the real findings)

These recur across clusters and should be fixed as **standards**, not folder-by-folder:

1. **No rotation/retention is the default.** Almost every writer appends a new timestamped file
   forever: `unified_guard` (5,965), `token_governance` (5,742), `pre_session` (254),
   `security` (283), `routing`, `budget/daily.jsonl` (205K lines). NTFS directory-listing
   degradation and git bloat are weeks away, not months.
2. **Phantom / audit-theater data presented as real signal.** `traces.jsonl` = 40 MB of all-zero
   token/duration rows; `staged_issues.jsonl` = 85 MB while state is `records: []`;
   `codegraph_effectiveness` = demo IDs with null precision/recall; `security/log_integrity_latest.json`
   = `targets: {}`; `command_matrix/latest.json` = `status: error`, all null. These inflate size
   **and** mislead.
3. **Staleness with no freshness guard.** `governance_intelligence` (12d), `usage_calibration` (12d),
   `review_intake`/`epic_reviews`/`pr_risk` (since Jun 1–2), 8 learning folders (12–17d).
   Worse: `harness_health` ingests stale `governance_intelligence` data **without flagging age**.
4. **Misleading-green quality gates.** Security `passed:true` while dep-scan skipped; 71% of token
   events classified "unknown" yet routing proceeds; `drift` score (32, "worsening") is a false
   alarm from a stale baseline. Green that isn't green is worse than red.
5. **Thin / empty / dead folders (structural sprawl).** `queue/` (empty), `workflows/` (.gitkeep
   only), `governance_review` (script never called), `claim_guard` (stubs), 7 single-file
   session folders, 7 micro learning folders. Folder-per-artifact adds depth and boilerplate with
   no locality benefit.
6. **Not gitignored → repo bloat & push hazard.** `execution/`, `decisions/`, `traces/`,
   `pre_session/`, `issue_intake/staged_issues.jsonl` are git-tracked runtime exhaust. The 85 MB
   file alone risks GitHub large-file warnings.
7. **Redundant stores, no documented authority.** `token_governance` per-run files duplicate
   `history.jsonl`; 5 overlapping intake queues; no `*_AUTHORITY.md` declaring which is canonical.

---

## 3. Prioritized actions (mapped to existing beads where they exist)

> Several findings already have beads — link the cleanup to them rather than duplicating.
> Existing: `sgfr.4` (trace sampling + **log rotation**), `4kt5.3` (rebuild pre_session manifest),
> `mrn7.1` (REGISTRY + **dead-code detector**), `mrn7.3` (unify collision, retire scripts),
> `mrn7` epic (Automation Consolidation & Hook Slimming).

### P0 — reclaim space + kill misleading-green (do first)

| Action | Reclaims | Bead |
|---|---|---|
| Add a shared **retention/rotation helper** (keep N latest + `*_latest.json`) and call it from `unified_guard`, `token_governance`, `security`, `pre_session`, `routing` writers; run once to prune. | ~150 MB, ~17k files | extend `sgfr.4`; new bead for the shared helper |
| Truncate/relocate `issue_intake/staged_issues.jsonl` (gzip to off-repo archive or git-LFS); state is already empty. | 85 MB | **new bead** |
| Stop writing phantom `traces.jsonl` rows until OTLP is wired; delete current 40 MB. | 40 MB | `sgfr.1`/`sgfr.4` |
| Compact `intake_queue.jsonl` to latest-record-per-id (1317→248) + sweep 395 stuck `processing`. | — (trust) | **new bead** |
| Remove `--no-deps` from `ci.yml` + `run-all-e2e.py`; install `pip-audit`. Security must actually gate deps. | — (trust) | `4kt5.x` quality gates |
| Delete/implement empty stubs: `security/log_integrity_latest.json` (`targets:{}`), `command_matrix` (error). | — (trust) | **new bead** |
| Gitignore `*.jsonl` under `execution/`, `decisions/`, `traces/`, `pre_session/`, and `issue_intake/staged_issues.jsonl`. | prevents regrowth | **new bead** |

### P1 — fix data quality + freshness

- Add **model→C/T-level inference** in the budget ledger writer to reclassify the 6,498 "unknown"
  events; removes the −10% target penalty and restores router confidence. (token/budget)
- Add **freshness guards**: `harness_health` warns if any ingested `latest.json` is >24h (fail >72h);
  apply to `governance_intelligence`, `usage_calibration`. (governance)
- **Re-anchor `drift/baseline.json`** to current approved structure, then wire drift into
  `daily_harness_audit.py --strict` so it's a real gate, not noise. (governance)
- Compact `budget/daily.jsonl` (205K lines / 25.7 MB) + delete orphaned `.bak` files. (token/budget)

### P2 — structural consolidation (folder sprawl)

- Collapse thin session folders into `session_snapshots/` (`preflight`, `recovery`, `go_mode`,
  `seed_state`, `auto_turn_thresholds`) and JSONL streams into `streams/`. 10 dirs → 2–3. (`mrn7`)
- Merge `harvest_trends/` + `release/` + `audits/` → `analytics/`. (learning)
- Retire dead: `queue/`, `workflows/`, `governance_review` (or wire it), `claim_guard` stubs,
  `codegraph_effectiveness` (demo). Use `mrn7.1` dead-code detector. (`mrn7.1`)
- Classify `ws_events/` as machine-local; move outside the repo tree. (learning)

---

## 4. Proposed standards (write these down once, enforce everywhere)

1. **Retention standard** — every `07_LOGS_AND_AUDIT/<folder>` writer keeps at most N dated files
   (default 30 days or 50 files) plus `*_latest.json`/`history.jsonl`. One shared helper, not
   per-script logic.
2. **`.gitignore` policy** — runtime exhaust (`*.jsonl` streams, per-session manifests, scan
   snapshots) is gitignored; only `latest.json`, `history.jsonl`, schemas, and `.gitkeep` are tracked.
3. **Freshness contract** — any artifact consumed by a gate carries `generated_at`; consumers fail
   loud on staleness rather than silently ingesting old data.
4. **Authority declaration** — each cluster with >1 store gets a short `*_AUTHORITY.md` naming the
   canonical file and labelling the rest derived/archive/retired.
5. **No audit theater** — a folder that emits only stub/demo/zero data is either wired to produce
   real data or deleted; "exists" is not "working" (mirrors the DoD §9 LIVE rule).

---

## 5. PDR completion & lifecycle tracking (Part 1 deliverable)

**Problem the user named:** no way to know when a PDR is complete or where it sits in the process.

**Root cause found:** PDRs declare a free-text `**Status:**` and a `**Beads:**` id, but those are
not reconciled against `bd`. Running the new generator shows **12 reconciliation warnings — every
active PDR either has no bead or points at a `trsk-*`/`mc-*` bead that does not exist in `bd`.**
The 4 newest PDRs (2026-06-16) and `TOKEN_ECONOMY_SPEC` all reference phantom beads.

**Delivered:**
- `08_PDRS/scripts/make_pdr_index.sh` — parses each PDR's `Status` + `Beads`, queries live `bd`
  state, derives a Definition-of-Done lifecycle stage (CAPTURE→…→OBSERVE), and flags drift
  (missing bead, no bead, declared-vs-live disagreement). `--check` mode exits non-zero for CI/pre-commit.
- `08_PDRS/PDR_INDEX.md` — generated, auto-regenerable, "do not hand-edit".

**Process recommendation:**
1. **Fix the linkage now** — for each active PDR, create or attach the real `bd` bead and replace
   the phantom `trsk-*`/`mc-*` id. A PDR with no live bead = not in the process.
2. **Make the index a gate** — add `bash 08_PDRS/scripts/make_pdr_index.sh --check` to the existing
   pre-commit/CI alongside the DoD/review-daemon checks, so PDR↔bead drift is caught automatically.
   This fits the existing `4kt5` "Quality Gates" epic.
3. **Single source of truth for status** = `bd` bead state (DoD §8/§9 define closed/LIVE); the PDR
   `Status:` line becomes declared *intent*, the index shows *reality*, the flag column shows the gap.

> v1 parser limitation to note: a PDR with two `**Beads:**` lines (e.g. `PDR_HARNESS_TELEMETRY_COVERAGE`)
> currently shows only the first; widen the grep when convenient.

---

## 6. Suggested next steps (for your approval — nothing destructive done yet)

1. **Approve P0** and I'll create the missing `bd` beads, then execute the prune/compaction
   (reversible: archives first, deletes second) on a session branch + PR.
2. **Decide retention defaults** (30 days vs 50 files) so the shared helper has a target.
3. **Confirm the intake authority** — keep `intake_queue.jsonl` as the spine? (my recommendation).
4. **Fix PDR↔bead linkage** — want me to draft the real beads for the 5 floating PDRs and rewrite
   their `Beads:` lines?
5. **Router note:** the `intake`→tier-2 downgrade rule blocked a subagent twice; flag if unintended.

_Original §1–6 above were read-only analysis. Execution log below._

---

## 7. EXECUTED 2026-06-16 (fan-out + serial)

**Disk:** `07_LOGS_AND_AUDIT/` **315 MB → 52 MB** (~263 MB reclaimed), **12,457 → 368 files**.
All deletions archived (gzip/tar) to off-repo `~/harness_cleanup_archive_2026-06-16/` (recoverable).

| Item | Result | How |
|---|---|---|
| unified_guard prune | 5,980 → 54 files (33.9 MB) | Wave-A subagent |
| token_governance prune | 5,755 → 56 files | Wave-A subagent |
| security snapshots prune | 287 → 53 files | Wave-A subagent |
| pre_session manifests | 254 → 31; traces/execution/decisions truncated | Wave-A subagent (91 MB) |
| ws_events prune | 9 → 5; routing left (under threshold) | Wave-A subagent |
| `staged_issues.jsonl` | 85 MB → removed (archived) | orchestrator |
| `intake_queue.jsonl` | 1317 → 248 lines (latest-per-id); only 4 truly "processing" | orchestrator |
| budget `.bak` files | 9 deleted (3.7 MB); daily.jsonl/ledger.jsonl untouched | Wave-A subagent |
| **Shared retention helper** | `scripts/log_retention.py` + `tests/test_log_retention.py` (5 tests pass); `--all` sweeps managed dirs | orchestrator |
| **CI dep-scan gate** | `ci.yml`: removed `--no-deps`, installs pip-audit, full scan blocking | orchestrator |
| **PDR↔bead linkage** | 4 beads created (zdnm/ckqr/gh4a/28iz); phantom `trsk-*` refs rewritten; ckqr+28iz → in_progress | orchestrator + bd |
| **PDR index** | regenerated; warnings 12 → 8 (remaining = historical/cross-tracker) | `make_pdr_index.sh` |

**Deferred to beads (need TDD, not safe to rush blind):** token model→C/T classification (`gh4a`),
freshness guards + drift baseline re-anchor (`zdnm`), unified-guard/token-gov strict-audit green
(`28iz`), folder consolidation of thin dirs (existing epic `mrn7`), `budget/daily.jsonl` ledger
compaction. Wire `log_retention.prune_dir()` into each writer + `make_pdr_index.sh --check` into CI
as part of `28iz` / `4kt5`.

**Not pushed.** Working tree holds all changes for review (branch `feat/auto-update-pr-branches`
already had 68 unrelated changes — recommend a dedicated cleanup branch + PR). 250 tracked-dump
deletions are staged-pending in the working tree; the rest were gitignored/untracked.
