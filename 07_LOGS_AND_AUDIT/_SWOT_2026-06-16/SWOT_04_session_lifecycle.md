# SWOT — Session & Execution Lifecycle cluster
**Audit date:** 2026-06-16  
**Cluster root:** `07_LOGS_AND_AUDIT/`  
**Auditor:** claude-sonnet-4-6 (automated SWOT sweep)

---

## Folder inventory

| Folder | Files | Size | Newest mtime | Has latest.json | Schema summary | Fresh/Stale |
|--------|------:|-----:|-------------|:---------------:|----------------|:-----------:|
| `pre_session/` | 255 | 333 KB | 2026-06-16 | Yes | Per-session boot manifest: branch, git status, MCP profile, routing context, governance. `latest.json` + timestamped `manifest_YYYYMMDD_HHMMSS.jsonl` archive. | **Fresh** |
| `preflight/` | 1 | 3.7 KB | 2026-06-01 | Yes | Full preflight result: lint/imports/tests stage array with pass/fail + raw output. Verbose (includes full pytest stdout). | **Stale** (15 days) |
| `recovery/` | 3 | 246 B | 2026-06-04 | Yes | Minimal lease/conflict/stale summary (`status`, `stale_count`, etc.). `.gitkeep` + `.json.bak` present. | Warm |
| `go_mode/` | 4 | 3.0 KB | 2026-06-01 | Yes | Task-selection + 7-factor confidence report with full `mission_packet`. Contains `.gitignore` and `.gitkeep`. | **Stale** (15 days) |
| `execution/` | 1 | 35.2 MB | 2026-06-16 | No | Append-only event log: `ts`, `mission_id`, `task_id`, `event_type`, hashed args/outputs, `idempotency_key`. 77 353 lines. | **Fresh** |
| `decisions/` | 1 | 10.2 MB | 2026-06-16 | No | Confidence/gate decision log: `ts`, `gate`, `input_score`, `band`, `action`, `reason`, `lesson`. 52 874 lines. | **Fresh** |
| `traces/` | 1 | 40.4 MB | 2026-06-16 | No | OTel GenAI JSONL stub: trace/span IDs, duration_ms (always 0), gen_ai attributes. 73 746 lines. OTLP export deferred. | **Fresh** (but dummy data) |
| `seed_state/` | 1 | 673 B | 2026-06-01 | No | Static mapping: GitHub epic/issue slug → bead ID. 14 entries. No versioning. | **Stale** (15 days) |
| `operations/` | 1 | 3.2 KB | 2026-06-04 | No | DR inventory v1: per-path RTO/RPO, size, recovery notes. Snapshot, not live. | Warm |
| `auto_turn_thresholds/` | 2 | 1.3 KB | 2026-05-30 | Yes | Calibration report: threshold recommendations derived from 5 observations rows (0 triggered). Duplicate representation: `latest.json` + `latest.md`. | **Stale** (17 days) |
| `AGENT_RUN_LOG.jsonl` (base) | 1 | 17.6 KB | 2026-06-04 | — | Per-run agent summary: task_id, model, role, confidence, tools_used, files_touched. 73 lines; first row is example/fixture data. | Warm |
| `active_sessions.sqlite3` (base) | 1 | 16 KB | 2026-06-04 | — | SQLite session registry. | Warm |

**Cluster totals: 272 files / 86.1 MB**  
Three large unbounded append-only JSONL files account for ~85.8 MB (99.6% of storage).

---

## Strengths

1. **Clear lifecycle separation.** Each folder maps to a discrete lifecycle phase (pre_session → preflight → go_mode → execution → decisions → traces), making the audit trail readable at a glance.

2. **latest.json convention.** Six of ten folders maintain a `latest.json` pointer, giving consumers a stable read path without parsing the entire archive. The pre_session `latest.json` schema is rich and actionable (MCP audit, routing context, governance risk, pack_version).

3. **Append-only integrity for core telemetry.** `execution.jsonl`, `decision_log.jsonl`, and `traces.jsonl` have opening `_comment` sentinel rows that self-document purpose and authorship. The idempotency keys in `execution.jsonl` support replay-safe ingestion.

4. **Stable script-to-folder wiring.** `scripts/pre_session_manifest.py` and `scripts/session_preflight.sh` have explicit, tested output paths (`CHROMATIC_PRE_SESSION_DIR` override supported). `check_agent_operations.py` validates `.gitkeep` presence. Contracts exist.

5. **DR inventory is present.** `operations/dr_inventory.json` correctly classifies `07_LOGS_AND_AUDIT` as P2 (non-blocking recovery), acknowledging logs are regenerable — an accurate risk posture.

---

## Weaknesses

1. **`pre_session/` has no rotation/cleanup.** `write_manifest()` appends a new timestamped `.jsonl` file on every invocation with no upper bound. 176 files were created on 2026-05-30 alone (likely a runaway loop or automation replay). At current cadence (~3–17 files/day during active use), this folder will reach 1 000+ files within weeks. No TTL, no max-count guard, no pruning hook exists anywhere in the codebase.

2. **Seven single-file folders.** `preflight/`, `execution/`, `decisions/`, `traces/`, `seed_state/`, `operations/`, and `auto_turn_thresholds/` each hold exactly 1–2 files. Each folder adds filesystem overhead (directory inode, `.gitkeep` boilerplate in some) without providing organisational value. This is structural bloat: a reader navigates 10 directories to find 10 files that could live in 2–3 directories.

3. **`traces.jsonl` is dummy/stub data (40.4 MB, 73 746 lines).** The opening sentinel says "OTLP export deferred." All `duration_ms` values are 0, `gen_ai.usage.input_tokens` and output tokens are 0. The file is the largest in the cluster yet contains zero actionable signal. It is accumulating phantom records from a feature that was never activated.

4. **`preflight/` and `go_mode/` latest.json are 15 days stale.** Preflight last ran 2026-06-01; go_mode selection last ran 2026-06-01. If these are expected to refresh each session, staleness indicates the session_boot_automation or session_preflight.sh is no longer writing results, or the workflow has diverged.

5. **`auto_turn_thresholds/` trained on n=5, n_triggered=0.** The calibration is statistically meaningless (5 observations, zero trigger events) yet the file carries `confidence: 0.82` in its frontmatter. No re-calibration schedule is defined.

6. **`AGENT_RUN_LOG.jsonl` contains fixture/example rows.** Lines 2–5 repeat `CHR-MISSION-DONE0001` twice with identical data — these are seeded example rows, not real run records. Real and synthetic data are mixed in the same file with no separator.

7. **`recovery/latest.json` reports `action_required: true` but no action taken.** The file shows `stale_count: 1` and `action_required: true`, dated 2026-06-04. No follow-up record exists. The flag is written but nothing consumes or clears it.

---

## Opportunities

1. **Implement pre_session/ rotation in `write_manifest()`.** A 10-line addition capping the archive to the 30 most recent files (or files younger than 14 days) would bound storage permanently. The 2026-05-30 spike (176 files) would be pruned on next run.

2. **Consolidate the single-file thin folders into a `session_snapshots/` group.** `preflight/`, `go_mode/`, `recovery/`, `seed_state/`, and `auto_turn_thresholds/` could be flattened:
   - `session_snapshots/preflight_latest.json`
   - `session_snapshots/go_mode_latest.json`
   - `session_snapshots/recovery_latest.json`
   - `session_snapshots/seed_state.json`
   - `session_snapshots/auto_turn_thresholds_latest.json`
   This collapses 5 directories into 1 with no loss of readability, reduces `ls` noise, and eliminates `.gitkeep` clutter.

3. **Consolidate `execution/`, `decisions/`, `traces/` under `streams/`.** Three single-JSONL folders become:
   - `streams/execution.jsonl`
   - `streams/decision_log.jsonl`
   - `streams/traces.jsonl`
   These are logically peer streams; grouping them mirrors the OTel "signal types" taxonomy (logs, events, traces).

4. **Gate or stub-out traces.jsonl until OTLP is live.** Stop appending 0-token phantom trace rows. Either wire a real OTel exporter or write traces only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. Deleting the current file would reclaim 40.4 MB immediately.

5. **Add a staleness alert to `check_agent_operations.py`.** Emit a warning when `preflight/latest.json` or `go_mode/latest.json` is older than N days. This turns a silent drift into an actionable CI signal.

6. **Promote `auto_turn_thresholds/latest.md` → wiki.** The file's own "Convergence Notes" say to do this. The `.md` duplicate of the `.json` is redundant once the wiki is updated; the folder can then hold only `latest.json`.

---

## Threats

1. **`pre_session/` unbounded growth is a git-history risk.** Even at ~1 KB/file the 254-file archive is already tracked (no `.gitignore` in that folder), and the 2026-05-30 runaway created 176 files in one day. A second runaway during a CI loop could commit thousands of files before anyone notices.

2. **`traces.jsonl` at 40.4 MB and growing will eventually break `git status`/`git diff` performance.** The file is not gitignored (no `.gitignore` in `traces/`). At 73 746 lines and growing unboundedly with every session, a 500 MB file within weeks is plausible.

3. **`execution.jsonl` at 35.2 MB, 77 353 lines, also unbounded.** Same risk as traces. No rotation, no archiving, no size gate. Will grow proportionally with harness activity.

4. **`recovery/latest.json` stale `action_required: true` flag.** If downstream automation ever gates on this flag, the uncleared stale state could block legitimate recovery workflows or trigger false-positive alerts.

5. **`seed_state/issue_to_bead.json` schema drift risk.** A static mapping with no version header or `updated_at` field. If bead IDs are reassigned or issues are closed, the file silently lies. No consumer validation is apparent.

---

## Cleanup Recommendations

### P0 — Do now (prevents unbounded growth / data integrity issues)

**P0-A: Add rotation to `write_manifest()` in `scripts/pre_session_manifest.py`**
- After writing `latest.json` and the new `manifest_*.jsonl`, enumerate existing `manifest_*.jsonl` files, sort by name (timestamp order), and delete any beyond the newest 30.
- Rationale: 254 archived manifests exist with no upper bound. The 2026-05-30 runaway proves a single automation error can create 176+ files. Cap at 30 covers 2–4 weeks at typical cadence.
- Target: `scripts/pre_session_manifest.py`, function `write_manifest()`, after line 231.

**P0-B: Gitignore or rotate `execution.jsonl`, `decision_log.jsonl`, and `traces.jsonl`**
- Add a `.gitignore` inside `execution/`, `decisions/`, and `traces/` to exclude `*.jsonl` from git tracking.
- Additionally, add a rotation/archive cron or session-start hook: rotate at 10 MB, keeping `*.jsonl` and `*.jsonl.1` (one prior generation).
- Rationale: Three files total 85.8 MB and grow with every session. None should be in git history. Traces are especially wasteful (all-zero token counts, OTLP deferred).
- Target: Create `execution/.gitignore`, `decisions/.gitignore`, `traces/.gitignore` each containing `*.jsonl`.

**P0-C: Stop writing phantom trace rows until OTLP is wired**
- In `02_RUNTIME/audit/two_log.py` (the trace emitter), gate trace writes on `os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")` or a harness config flag. If unset, skip. Delete the current `traces.jsonl` (40.4 MB of zeros).
- Rationale: `traces.jsonl` is the largest file in the cluster (40.4 MB) and contains zero actionable signal.

### P1 — Do soon (structural smell / staleness / data quality)

**P1-A: Consolidate thin single-file folders into `session_snapshots/`**
- Move `preflight/latest.json` → `session_snapshots/preflight_latest.json`
- Move `recovery/latest.json` → `session_snapshots/recovery_latest.json`
- Move `go_mode/latest.json` → `session_snapshots/go_mode_latest.json`
- Move `seed_state/issue_to_bead.json` → `session_snapshots/seed_state.json`
- Move `auto_turn_thresholds/latest.json` → `session_snapshots/auto_turn_thresholds.json`
- Update all consumer paths: `session_preflight.sh` (line 47), `task_runner.py`, `go_mode.py`.
- Optionally move `execution/`, `decisions/`, `traces/` into `streams/`.
- Rationale: 7 single-file folders is a structural smell. A developer navigates 7 directories to read 7 files. Consolidation has zero data loss and reduces `ls` depth significantly.

**P1-B: Purge `pre_session/` archive down to newest 30 files**
- One-time: `Get-ChildItem pre_session -Filter "manifest_*.jsonl" | Sort-Object Name | Select-Object -SkipLast 30 | Remove-Item`
- Removes 224 files (all pre-June, including the 2026-05-30 runaway spike).
- Rationale: Historical per-session manifests have no long-term audit value beyond recent coverage.

**P1-C: Separate fixture rows from real rows in `AGENT_RUN_LOG.jsonl`**
- Remove or replace the 4 duplicate `CHR-MISSION-DONE0001` example rows with a comment sentinel similar to `execution.jsonl`.
- Add `schema_version` and `_comment` header row to match the `execution.jsonl` convention.
- Rationale: Mixed fixture/real data makes query results unreliable.

**P1-D: Clear `recovery/latest.json` `action_required: true`**
- Investigate the `stale_count: 1` finding from 2026-06-04; resolve the stale lease or explicitly acknowledge it with a timestamped note.
- Rationale: An unactioned flag dated 12 days ago is either stale state or a real issue being silently ignored.

### P2 — Housekeeping (low urgency)

**P2-A: Add `updated_at` and `schema_version` to `seed_state/issue_to_bead.json`**
- Rationale: The file has no freshness marker. As issues close and epics complete, drift is invisible.

**P2-B: Remove `auto_turn_thresholds/latest.md`** (after wiki promotion)
- The `.md` duplicates the `.json` for human readability. Promote to wiki per the file's own note, then delete the `.md`.
- Rationale: Two representations of the same data in the same folder, one of which says to move it elsewhere.

**P2-C: Add `schema_version` to `preflight/latest.json`**
- The preflight schema embeds full pytest stdout (3.7 KB) with no version header. If the stage structure changes, consumers break silently.

**P2-D: Add staleness check to `check_agent_operations.py`**
- Emit a warning (non-fatal) when `preflight/latest.json` or `go_mode/latest.json` mtime is older than 7 days.
- Rationale: Both are 15 days stale today; nothing flagged it.

---

## Cross-cluster notes

- **`operations/dr_inventory.json`** references `07_LOGS_AND_AUDIT` as 202 MB (P2). The actual cluster-total is 86 MB as of this audit; the DR inventory figure appears to include the full `07_LOGS_AND_AUDIT` tree (other clusters). That figure will balloon rapidly if `execution.jsonl`/`traces.jsonl` grow unchecked — the DR note "Historical logs not strictly required for operation" is correct but understates the git-history risk.
- **`active_sessions.sqlite3`** at the base level is 16 KB and warm (last written 2026-06-04). It sits outside the cluster folder structure, alongside `AGENT_RUN_LOG.jsonl`. Both would benefit from explicit mention in the DR inventory and a `.gitignore` entry — SQLite WAL files and JSONL session logs should not be committed.
- **`go_mode/` `.gitignore`** correctly excludes `latest.json` and `missions/`. The `pre_session/`, `execution/`, `decisions/`, and `traces/` folders have no such protection and need equivalent `.gitignore` entries (see P0-B above).
- The `auto_turn_thresholds` calibration (n=5, n_triggered=0) is too thin to trust. The threshold recommendations should be treated as defaults, not calibrated values, until at least 20 triggered observations are collected.
