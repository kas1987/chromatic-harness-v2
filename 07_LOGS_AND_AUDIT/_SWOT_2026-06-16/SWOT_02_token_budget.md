# SWOT — Token & Budget cluster

**Audit date:** 2026-06-16
**Auditor:** Claude (Sonnet 4.6), automated sweep of 07_LOGS_AND_AUDIT/

---

## Folder inventory

| Folder | Files | Total size | Newest mtime | Has latest.json | Schema summary | Fresh / Stale |
|---|---|---|---|---|---|---|
| token_governance/ | 5742 | 38.3 MB | 2026-06-16 11:35 | Yes | Per-run audit: 4 checks (session_context_report, audit_mcp_context, validate_workflow_token_governance, daily_harness_audit_strict). Writes: run-stamped .json + latest.json + history.jsonl + latest.md | **Fresh** (updated this session) |
| budget/ | 20 | 31.3 MB | 2026-06-16 11:35 | No (forecast_latest.json) | ledger.jsonl (per-decision rows with axis/cost_center/usd), daily.jsonl (per-event spend entries), forecast_latest.json (boot/burn/limits/forecast), forecast_history.jsonl, monthly.json; 3 orphaned .bak files from 2026-06-02 | **Partially stale** — forecast_latest.json: 2026-06-02; daily.jsonl last entry: 2026-06-05; ledger.jsonl: 2026-06-16 |
| usage_calibration/ | 8 | 0.83 MB | 2026-06-04 17:53 | No | calibrated_caps.json (five_hour/seven_day wtok caps, confidence=prov, spread_pct=441/397), rollup.json (weekly/daily/monthly wtok by session+model), weight_table.json (canonical pricing weights), epochs.json (single epoch e1 since init), wtok_events.jsonl, snapshots_archive.jsonl | **Stale** (last update 2026-06-04, 12 days ago) |
| command_matrix/ | 2 | 0.5 KB | 2026-06-04 17:54 | Yes | latest.json: status=error, command_count=null — pytest temp file missing; .bak from 2026-06-02 | **Broken + stale** |
| control_plane/ | 1 | 0.5 KB | 2026-06-16 11:35 | No | routing_policy_overlay.json: schema=routing_policy_overlay/v1; c_to_t_threshold=4, staleness_fallback=true (Axis P signal missing/stale >300s — conservative mode), allow_paid_spill=false | **Fresh** but in degraded/fallback state |

**Cluster totals: 5,773 files, ~70.4 MB**

---

## Strengths

1. **Closed-loop automation is real.** `token_governance_closed_loop.py` runs 4 checks, writes latest.json + history.jsonl + latest.md, enqueues bead suggestions to the intake queue, and is wired to scripts consumed by `session_start.py`, `harness_kpi_console.py`, `log_integrity_check.py`, and `generate_dashboard.py`. The governance loop is genuinely connected to downstream tooling, not dead letters.

2. **Schema is well-defined and consistent within each subsystem.** `ledger.jsonl` entries are consistent (decision_id, ts, axis, cost_center, tokens, usd, confidence). `weight_table.json` is the canonical pricing reference with a clear versioning note. `token_governance` per-run files are structurally identical to latest.json (confirmed by sampling oldest and newest).

3. **history.jsonl provides a compact, appendable audit trail.** The JSONL approach (one line per run) for `token_governance/history.jsonl` and `budget/forecast_history.jsonl` avoids the per-file explosion problem that plagues the individual run files.

4. **Control plane routing reacts to real signals.** `routing_policy_overlay.json` is freshly generated (this session), reflects live staleness detection (Axis P signal >300s stale), and drives the `c_to_t_threshold` used by the router — functional governance linkage.

5. **`usage_calibration/weight_table.json` is the canonical pricing source.** Well-commented, versioned (2026-06-pricing), cross-referenced to governance CSV. Single source of truth for wtok normalization.

---

## Weaknesses

1. **token_governance/ has 5,742 individual per-run .json files with zero rotation or retention logic.** `_write_reports()` in `token_governance_closed_loop.py` (line 401) writes `token_governance_{ts}.json` every invocation with no cap, no cleanup, no max-file-count guard. At 739–1,099 files/day during active periods, this will hit filesystem limits (NTFS inodes are not a practical concern, but >5K files in one flat directory causes `ls`/Explorer/glob slowdowns and balloons repo size). The folder is growing unboundedly.

2. **71% of ledger events are classified "unknown" — the core telemetry signal is degraded.** As of 2026-06-16, `confidence_band` in `token_governance/latest.json` shows: 9,148 total events, 6,498 unknown (71.03%), $0 attributed to unknowns (so cost attribution is intact for P/D axes). The "unknown" classification means `c_level` and `t_level` are null in those ledger rows — model routing metadata is not being captured, which makes the `cost_center` fields only partially informative. The forecast system already penalizes this: `-unknown_warning(10.0%)` subtracts 10% from the weekly spend target.

3. **`command_matrix/latest.json` is broken (status=error) and stale (2026-06-04).** The error references a pytest temp file that no longer exists (`pytest-5713/test_summarize_fail_open_on_ba1/nope.yaml`). This means the command-matrix check is non-functional. Consumers that read `latest.json` get null `command_count` and null `in_sync`.

4. **`usage_calibration/` is 12 days stale and has very low confidence.** `calibrated_caps.json` shows `confidence: "prov"` (provisional), `spread_pct: 441` for five_hour and `397` for seven_day — uncertainty bands >4x the estimated cap. Only 3 data points feed seven_day. The calibration has not run since 2026-06-04 and its forecasts are unreliable.

5. **`budget/daily.jsonl` has 205,543 lines (25.7 MB) with no rotation or compaction.** 1,920 lines have `source: "ledger:unknown"` (from the early period when the bridge was writing zero-amount unknown entries). The file appears to grow without bound. Three orphaned `.bak` files from 2026-06-02 remain, suggesting a failed migration was partially cleaned up but not finished.

6. **`forecast_latest.json` is stale (2026-06-02) and reflects an over-cap state.** `weekly_spent_usd: 112.5` against `cap_usd: 100.0` — the forecaster ran into a boundary condition and has not refreshed since. The `axis_prepaid` block in `token_governance/latest.json` confirms `fresh: false, status: "red"` for this data source, which cascades to the overall governance status=red and `staleness_fallback: true` in the control plane.

---

## Opportunities

1. **Collapse per-run .json files into history.jsonl, implement a retention window.** The per-run files are exact duplicates of what's already in `history.jsonl`. Only `latest.json` and `history.jsonl` are consumed by downstream scripts. Deleting per-run files older than N days (e.g., 7–14) would eliminate ~5,700 files immediately, drop storage to under 1 MB for this folder, and make the directory fast to traverse.

2. **Fix the "unknown" classification at the source.** The 71% unknown rate comes from `c_level`/`t_level` being null in ledger entries. The cost_center model field is populated (claude-opus-4-8, claude-sonnet-4-6), so the model is known — the gap is the C/T level tagging. Adding model→C/T level inference in the ledger writer would reclassify the majority of unknowns and remove the -10% target penalty, recovering ~$7–10/week of usable budget headroom.

3. **Re-run usage_calibration to get current caps.** The calibration has been stale 12 days. Running `wtok_events.jsonl` through the calibration pipeline with recent session data would refresh cap estimates and reduce the spread from 440% to something actionable.

4. **Compact `budget/daily.jsonl` and remove `.bak` orphans.** The 205K-line file can be compacted to a rolling 90-day window; older data is already summarized in `monthly.json`. The three `.bak` files from 2026-06-02 serve no purpose.

5. **Fix and re-enable the command_matrix check.** The error is a stale pytest artifact path — the check itself may be trivially fixable. A working `command_matrix/latest.json` would add `in_sync` and `command_count` signals to the governance dashboard.

6. **Add a staleness guard to forecast_latest.json refresh.** The forecast is updated by `portfolio_token_forecast` refresh step but wrote `fresh: false`. Adding a staleness-triggered re-fetch (or failing louder when stale > N hours) would prevent the control plane from operating in `staleness_fallback` mode silently for days.

---

## Threats

1. **Unbounded token_governance/ growth will cause operational problems.** At peak cadence (1,099 files on 2026-06-06), the directory could reach 10K–20K files within weeks. Windows Explorer and glob operations degrade sharply above ~5K flat-directory files. The `.gitignore` and repo management tooling may include these in diff/status scans, slowing git operations significantly.

2. **Persistent status=red degrades signal value.** The governance loop has been red for the majority of its history (visible in history.jsonl: first 2 entries on 2026-05-30 are red, status turned green only after a hotfix). If red is the chronic baseline state due to stale forecast data, operators will normalize it and miss genuine new failures.

3. **71% unknown events corrupt the router's spend model.** If the router uses the confidence band to gate paid-spill decisions, a permanently degraded confidence signal means `allow_paid_spill` is structurally suppressed — the model may be more conservative than intended, not because of actual quota pressure but because of classification failures in the ledger.

4. **`budget/daily.jsonl` size will cause read timeouts.** At 25.7 MB / 205K lines and growing, scripts that read or scan this file (e.g., for daily spend aggregation) will slow proportionally. A script doing a full read every session-start or governance run adds non-trivial latency.

5. **`.bak` file accumulation indicates migration risk.** Three backup files from the same 2026-06-02 hour suggest a partially-run migration script. If that migration is re-attempted without removing the orphans first, it may double-backup or fail on conflict.

---

## Cleanup Recommendations

### P0 — Critical / Do Now

**P0-A: Rotate token_governance/ per-run files — implement retention, delete all but last 14 days**
- Action: Add a `_prune_old_runs(out_dir, keep_days=14)` call at the end of `_write_reports()` in `scripts/token_governance_closed_loop.py`. Delete any `token_governance_YYYYMMDD_*.json` older than 14 days. Run once manually to purge the 5,739 existing files (keep only the 91 from 2026-06-16 and the latest.json/history.jsonl/latest.md).
- Rationale: Eliminates 5,700+ files (38+ MB), makes directory fast, eliminates unbounded growth. The data is already in `history.jsonl`.
- Folder: `token_governance/`

**P0-B: Fix command_matrix check — remove stale pytest path reference**
- Action: Investigate and fix `scripts/` code that generates `command_matrix/latest.json`. The error references a now-deleted pytest temp file. Either make the check path-independent or add a guard. Delete `latest.json.bak`.
- Rationale: Broken status=error means this governance signal is dark. `command_count` and `in_sync` are both null.
- Folder: `command_matrix/`

### P1 — High Priority / This Week

**P1-A: Fix the "unknown" event classification — add model→C/T level inference in ledger writer**
- Action: In the ledger writing code, add a lookup table mapping known model names (claude-opus-4-8 → C4/T4, claude-sonnet-4-6 → C3/T3, etc.) to populate `c_level`/`t_level` on events where the model is known but C/T is null. This will reclassify most of the 6,498 unknowns.
- Rationale: 71% unknown events suppress spend target by 10% ($7–10/week), degrade router confidence, and make cost_center data mostly non-actionable. Model is already captured — C/T inference is a cheap inference step.
- Folder: `budget/ledger.jsonl` (fix in source script)

**P1-B: Compact `budget/daily.jsonl` and remove orphaned .bak files**
- Action: Archive daily.jsonl entries older than 90 days to `daily.jsonl.archive`, truncate live file. Delete the three `.bak` files from 2026-06-02 (total ~3.7 MB orphaned backups).
- Rationale: 205K-line / 25.7 MB file grows without bound. `.bak` files are from a completed migration.
- Folder: `budget/`

**P1-C: Re-run usage_calibration pipeline**
- Action: Trigger calibration run to refresh `calibrated_caps.json`, `rollup.json`, and `wtok_events.jsonl` with data from 2026-06-04 through today. Target: reduce spread_pct from ~440% to <100%.
- Rationale: Caps are provisional with 440% spread — the system is flying blind on quota limits. 12 days of data are missing.
- Folder: `usage_calibration/`

### P2 — Improvement / Next Sprint

**P2-A: Add staleness alerting to forecast refresh**
- Action: Add a check in `token_governance_closed_loop.py` that fails with a distinct `warn` (not `fail`) if `forecast_latest.json` is older than 24 hours and `fresh: false`. Add a re-fetch attempt before falling back.
- Rationale: The control plane has been in `staleness_fallback: true` for 14 days without a loud alert. This silently conservatizes routing.
- Folder: `token_governance/`, `budget/`

**P2-B: Add `latest.json` to budget/ as a canonical fresh-state file**
- Action: The `budget/` folder has no `latest.json`. Consumers of `forecast_latest.json` have to know the non-standard name. Standardize: write/symlink `budget/latest.json` → `forecast_latest.json`, matching the convention of every other folder in this cluster.
- Rationale: Schema consistency across the cluster; makes `log_integrity_check.py` patterns uniform.
- Folder: `budget/`

**P2-C: Add `.gitignore` for token_governance per-run files**
- Action: Add `token_governance/token_governance_*.json` to `07_LOGS_AND_AUDIT/.gitignore` (not latest.json/history.jsonl/latest.md). Keep the canonical files tracked.
- Rationale: Even after rotation, per-run files should not be committed. Prevents git status/diff from scanning thousands of log files.
- Folder: `token_governance/`

---

## Cross-cluster notes

- The `daily_harness_audit_strict` check (which drives the red status here) is a cross-cluster dependency — this cluster's health is coupled to whatever `scripts/daily_harness_audit.py --strict` checks. If that check covers other clusters (e.g., 06_GOVERNANCE, 08_ALERTS), a red in another cluster propagates a red into token governance. The token_governance SWOT should not be read in isolation.
- `control_plane/routing_policy_overlay.json` is marked stale due to Axis P signal missing >300s, but this file is fresh (2026-06-16). The "staleness" is of the upstream quota API call, not this file. This is a naming confusion risk: the file is current, its input data is not.
- The `usage_calibration/weight_table.json` references `C:/.00_Governance/model-effort-routing.csv` as the canonical pricing source. If that CSV changes (e.g., for new models), the weight_table.json must be manually bumped. No automated sync or drift check is in place.
- Total cluster size (38.3 + 31.3 + 0.83 + 0.0005 + 0.0005 MB) = **~70.4 MB**, of which ~38.3 MB (54%) is in token_governance per-run files that are fully redundant with history.jsonl. Post-P0-A cleanup, the cluster should be under 35 MB.
