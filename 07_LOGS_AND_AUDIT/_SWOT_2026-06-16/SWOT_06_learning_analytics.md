# SWOT — Learning & Analytics cluster

**Audited:** 2026-06-16  
**Auditor:** SWOT agent (repo-cleanup initiative)  
**Scope:** `07_LOGS_AND_AUDIT/` — Learning & Analytics long-tail folders  
**Total cluster:** 45 files, ~3.93 MB

---

## Folder inventory

| Folder | Files | Size | Newest mtime | Has latest.json | Schema summary | Fresh/Stale |
|--------|------:|-----:|-------------|:---------------:|----------------|:-----------:|
| `routing/` | 15 | 3.75 MB | 2026-06-16 | No | Daily JSONL per-day (`routes_YYYYMMDD.jsonl`); event_type, threshold, provider, tier, reasons | **ACTIVE** |
| `learning_tiers/` | 2 | 62.7 KB | 2026-05-30 | Yes | Evidence/need pyramid (E0–E4 × N1–N4), 65 learnings, delta, top-ranked list | STALE (17d) |
| `ws_events/` | 10 | 14.2 KB | 2026-06-02 | No | Per-mission CHR-HANDOFF JSONL (magnet events, synthesis gate, decisions); 1 cli-test file | STALE (14d) |
| `baseline/` | 4 | 4.3 KB | 2026-05-30 | No | MCP/hook/env KPI scorecards per surface (app/cli/cursor/vscode) with warn/max/status | STALE (17d) — **gitignored** |
| `codegraph_effectiveness/` | 3 | 1.4 KB | 2026-05-30 | No (`summary_latest.json`) | A/B CSV runs + JSON/MD summary; 2-row demo dataset only | STALE (17d) |
| `collision/` | 3 | 2.6 KB | 2026-06-04 | No (`*_latest.json`) | claim_log.jsonl (lease grant/deny events) + file_collision_latest + heartbeat_latest | STALE (12d) — gitignored |
| `audits/` | 1 | 3.5 KB | 2026-06-03 | No | One-off markdown audit of review-intake PDR vs harness layout | STALE (13d) |
| `root_artifacts/` | 2 | 3.9 KB | 2026-06-16 | No (`latest_root_artifact_hygiene.json`) | Dry-run hygiene report (deletions planned); plus static cleanup narrative MD | **ACTIVE** |
| `harvest_trends/` | 2 | 659 B | 2026-06-01 | Yes | Single-rig duplicate-ratio snapshot from `.agents/harvest/latest.json` | STALE (15d) |
| `release/` | 2 | 438 B | 2026-06-01 | Yes | GO/NO-GO quality+security score snapshot (1 timestamped + latest) | STALE (15d) |
| `workflows/` | 1 | 0 B | 2026-06-01 | No | `.gitkeep` placeholder only — no data | PLACEHOLDER |

---

## Strengths

1. **routing/ is actively written and well-structured.** Daily-partitioned JSONL files, written by `02_RUNTIME/router/pipeline/audit.py` on every routing decision, with a lazy-rotation mechanism in the companion `~/.claude/.agents/router/log.jsonl`. Clear naming convention, gitignored (local-only), 3.75 MB of real telemetry.

2. **Consumed by scripts, not orphaned.** Every folder except `audits/` and `workflows/` has at least one named script producing or reading it: `compute_learning_tiers.py`, `summarize_harvest_trends.py`, `codegraph_effectiveness_scorecard.py`, `baseline_audit.py`, `file_collision_gate.py`, `root_artifact_hygiene.py`, `release_readiness.py`. The cluster is not random throw-away data.

3. **Gitignore discipline is mostly correct.** `routing/*.jsonl`, `ws_events/*.jsonl`, `workflows/*.jsonl`, `baseline/`, `collision/*.jsonl`, and `collision/*_latest.json` are all gitignored. The `.gitkeep` pattern correctly preserves directory stubs. `root_artifacts/latest_root_artifact_hygiene.json` is tracked (non-scratch artifact).

4. **ws_events/ schema is purposeful.** Per-mission JSONL replay feeds the WebSocket event bus (documented in `docs/console/WEBSOCKET_EVENT_BUS.md`); architecture is coherent with a Redis fanout path for multi-instance scale.

5. **learning_tiers/ schema is the most information-rich.** 62 KB, structured E×N pyramid, evidence tiers, delta tracking, top-10 ranked learnings — genuine analytics artifact feeding the learning reliability system.

---

## Weaknesses

1. **Extreme staleness across 9 of 11 folders.** Eight folders have not been updated since May 30 – June 4 (12–17 days ago). Only `routing/` and `root_artifacts/` show same-day activity. The learning pipeline, harvest trends, codegraph, baseline, collision, ws_events, release, and audits folders appear to have run once (at harness setup) and then stopped. If the underlying scripts are not being called regularly, the data is misleading rather than informative.

2. **codegraph_effectiveness/ is a demo skeleton.** Two data rows (`demo-001`, with/without mode, identical timestamps), `impact_precision` and `impact_recall` columns are null across the board. No real A/B trials have been logged. This is test scaffold data presented as analytics output.

3. **Long tail of 1–3 file folders is a structural smell.** Seven of the eleven folders contain 1–3 files and represent <= 5 KB each (`harvest_trends`, `codegraph_effectiveness`, `collision`, `workflows`, `baseline`, `release`, `audits`). The cognitive overhead of 11 separate directory entries outweighs the organizational benefit.

4. **workflows/ is a pure placeholder.** A `.gitkeep`-only directory with 0 bytes of actual data. The script producing workflow data (`workflow_go.py`, `docs/workflows/WORKFLOW_RUN_LOG.jsonl`) writes to a *different* location; this folder may never have been intended to receive data.

5. **ws_events/ naming is inconsistent.** Files use two schemes: `CHR-HANDOFF-<hex>.jsonl` (hash suffixes, 6 duplicates of near-identical 1060-byte content) and `CHR-HANDOFF-<N>.jsonl` (numbered). Both coexist with `cli-test.jsonl`. The hash-suffixed files appear to be deduplication failures from a bursty creation event on 2026-05-30.

6. **baseline/ is gitignored but present on disk.** The entire folder is excluded from version control, so its 4 files (app/cli/cursor/vscode scorecards) exist only locally. This makes the data ephemeral and unverifiable across machines. The `overall: "over"` status in `app.json` (hook_high finding) is unresolved and invisible to CI.

7. **collision/ gitignore excludes all meaningful content.** `claim_log.jsonl` and both `*_latest.json` files are gitignored, so the folder carries zero tracked state. The heartbeat shows `missed_heartbeats_detected` (stale lease `lease-stale`) — a test artifact or a real missed heartbeat that was never resolved.

8. **No rotation policy on routing/ beyond the source-level cap.** The daily JSONL files in `routing/` grow unbounded on disk (3.75 MB across 15 days, with a 752 KB spike on June 1 and 782 KB on June 3). There is no `--max-days` trim or archival rule; the companion `~/.claude` log has a 2000-line cap but the repo-side daily files do not.

---

## Opportunities

1. **Consolidate thin analytics folders into a single `analytics/` sub-cluster.** `harvest_trends/`, `codegraph_effectiveness/`, `learning_tiers/`, and `release/` could merge under `07_LOGS_AND_AUDIT/analytics/` with `latest_*.json` naming. Reduces 8 directories to 1, halves the directory-listing noise without data loss.

2. **Retire `workflows/` now.** It is a `.gitkeep` placeholder. If the JSONL runtime log belongs here, wire the script. If it belongs under `docs/workflows/`, remove this entry. A dead placeholder wastes cognitive budget.

3. **Add a routing/ rotation cron or git-hook.** Cap rolling window to 14 days (delete `routes_YYYYMMDD.jsonl` older than 14 days). This prevents the folder from silently growing into a multi-MB log dump.

4. **Graduate codegraph_effectiveness/ to real trials or retire it.** The 2-row demo dataset is misleading. Either: (a) instrument real `with`/`without` CodeGraph sessions, or (b) archive the demo data and document the method as "not yet active".

5. **Promote baseline/ content into CI.** Currently gitignored and only relevant on the local machine. Moving the `overall: "over"` hook_high alert to a tracked `latest_baseline_summary.json` (single-key pass/fail) would make it actionable in CI without committing verbose scorecard JSON.

6. **ws_events/ dedup + archive.** Remove the 6 hash-duplicated CHR-HANDOFF files (1060B each, same structure, same date). Archive numbered `CHR-HANDOFF-1/2/3.jsonl` as reference examples or delete once the event bus is validated. Keep only `cli-test.jsonl` as the live test stream.

7. **audits/ could become a rolling file.** A single timestamped markdown file per audit event creates a sparsely-populated directory. Consolidate into `audit_log.jsonl` with one JSON record per audit, keeping the markdown prose in `08_PDRS/` where it already partly lives.

---

## Threats

1. **Stale data gives false confidence.** A consumer reading `learning_tiers/latest.json` sees `2026-05-30` data as "current" without a staleness check. The `pyramid` shows all learnings stuck at E0 (zero promotions), all deltas at zero — this looks like a frozen or broken pipeline rather than genuine stability.

2. **collision/ heartbeat `missed_heartbeats_detected` is unresolved.** The `lease-stale` entry suggests either a test artifact that was never cleaned up, or a real missed heartbeat from a previous session. If the collision guard is active, a stale heartbeat could mask real collisions.

3. **routing/ files are gitignored but in the repo working tree.** If a developer runs `git clean -fd`, routing logs are deleted silently. Since they are the only source of router-decision history not covered by the `two_log` audit, their loss is undetected until a debugging session needs them.

4. **Naming drift risk.** `codegraph_effectiveness/` uses `summary_latest.json` (not `latest.json`), `collision/` uses `*_latest.json` suffixes, `release/` uses `latest.json`, `learning_tiers/` uses `latest.json`. No cluster-wide convention; scripts must hard-code individual paths.

5. **ws_events/ JSONL timestamps use epoch-ms integers (cli-test) vs ISO-8601 strings (CHR-HANDOFF).** Mixed timestamp format within the same folder increases parser fragility.

---

## Cleanup Recommendations

### P0 — Act now (correctness / hygiene risk)

| # | Action | Rationale | Target |
|---|--------|-----------|--------|
| P0-1 | **Delete or archive `workflows/` directory.** Remove the `.gitkeep` placeholder and eliminate the dead stub. If the folder is intended for future use, document the plan in `CHROMATIC_TREES.md`. | Zero bytes of data; misleads any directory census. | `07_LOGS_AND_AUDIT/workflows/` |
| P0-2 | **Resolve `collision/` heartbeat stale-lease artifact.** Either delete `heartbeat_latest.json` if it is a test fixture, or re-run the collision gate to reset it. | `missed_heartbeats_detected` for `lease-stale` is ambiguous noise; if real, it is a silent collision-guard failure. | `07_LOGS_AND_AUDIT/collision/heartbeat_latest.json` |
| P0-3 | **Deduplicate `ws_events/` hash-suffixed files.** Remove the 6 `CHR-HANDOFF-<hex>.jsonl` files (created in a 10-minute burst on 2026-05-30, identical 1060B structure). Keep the numbered files as reference. | Storage is trivial (~6 KB) but the naming pattern will accumulate with each test run if not capped. | `07_LOGS_AND_AUDIT/ws_events/` |

### P1 — Address this sprint (structure / efficiency)

| # | Action | Rationale | Target |
|---|--------|-----------|--------|
| P1-1 | **Add a routing/ retention policy: delete files older than 14 days.** Add a one-liner to `release_files.py` or a new `scripts/rotate_routing_logs.py` called from `session_closeout.py`. | No cap = indefinite growth; 3.75 MB in 15 days projects to 90 MB/year. | `07_LOGS_AND_AUDIT/routing/`, `scripts/session_closeout.py` |
| P1-2 | **Consolidate thin analytics folders.** Merge `harvest_trends/`, `release/`, and `audits/` outputs under `07_LOGS_AND_AUDIT/analytics/` with clear sub-names (`harvest_trends_latest.json`, `release_latest.json`). Update the 3 producer scripts. Reduces 3 directories to 0 (content absorbed). | 5 files totaling < 5 KB across 3 directories is directory-count bloat with no access-locality benefit. | `harvest_trends/`, `release/`, `audits/` |
| P1-3 | **Add a freshness guard to `learning_tiers/latest.json`.** If the file is more than 7 days old, emit a CI warning. The `validate_claude_harness.py` or `harness_health_check.py` scripts are natural insertion points. | 17-day-old learning tier data is undetected and may be referenced as current by consumers. | `scripts/validate_claude_harness.py` |
| P1-4 | **Standardize naming to `latest.json` across the cluster.** `codegraph_effectiveness/summary_latest.json` and `collision/*_latest.json` deviate from the dominant `latest.json` convention. Rename and update script constants. | Naming inconsistency forces every consumer to hard-code individual paths. | `codegraph_effectiveness/`, `collision/` |

### P2 — Deferred / strategic

| # | Action | Rationale | Target |
|---|--------|-----------|--------|
| P2-1 | **Either activate codegraph A/B logging or archive the demo data.** Add a session hook that calls `codegraph_effectiveness_scorecard.py log` after each bead close, or mark the folder as `[INACTIVE-DEMO]` in `CHROMATIC_TREES.md`. | 2 demo rows with null precision/recall are not analytics; they create false confidence in the metric system. | `07_LOGS_AND_AUDIT/codegraph_effectiveness/` |
| P2-2 | **Promote baseline/ hook_high alert to a tracked artifact.** Extract `hook_high.status` from each surface JSON into a single `baseline_health_latest.json` that IS committed. Keep the verbose per-surface files gitignored. | The `over` status on hook_high is actionable but invisible outside the local machine. | `07_LOGS_AND_AUDIT/baseline/`, `scripts/baseline_audit.py` |
| P2-3 | **Unify ws_events/ timestamp format.** Standardize to ISO-8601 across all JSONL writers (cli-test uses epoch-ms; CHR-HANDOFF files use ISO-8601). | Mixed formats increase event bus parser fragility. | `02_RUNTIME/console_api/event_store.py`, `scripts/ws_publish_event.py` |
| P2-4 | **Consider retiring `ws_events/` as a repo-side folder.** The WebSocket event bus is already gitignored for `*.jsonl`. If Redis is the production path, per-mission JSONL files are local-instance replay buffers that have no repo-side value. Document as "machine-local only" or move outside the repo tree. | Gitignored JSONL in a repo folder is misleading about the data's persistence guarantees. | `07_LOGS_AND_AUDIT/ws_events/`, `docs/console/WEBSOCKET_EVENT_BUS.md` |

---

## Cross-cluster notes

- **Overlap with governance cluster:** `routing/` data feeds `02_RUNTIME/audit/two_log.py` (the governance two-log audit spans), so it is partially duplicated in `07_LOGS_AND_AUDIT/governance_intelligence/history.jsonl`. The routing daily files are additive, not duplicative, but consumers should be aware both sources exist.
- **Overlap with session-lifecycle cluster:** `collision/claim_log.jsonl` records lease grant/deny events that are also visible via `claim_guard/` in this same audit tree. These two folders should be rationalized — collision covers file-path conflicts, claim_guard covers bead task claims; make sure they are not logging the same lease events to both locations.
- **Overlap with intake cluster:** `harvest_trends/` reads from `.agents/harvest/latest.json` which is also consumed by `session_start.py`. A single pre-session hook snapshot could serve both; `harvest_trends/latest.json` appears redundant with that upstream source.
- **root_artifacts/ is genuinely useful and actively maintained** (updated today). It should remain standalone and not be merged into a catch-all analytics folder.
- **learning_tiers/ is the highest-value folder in the cluster** despite its staleness. The 62 KB structured pyramid is unique data not replicated elsewhere. Priority for re-activation (ensure `compute_learning_tiers.py` runs as a post-session hook or nightly cron).
