# SWOT — Intake & Triage cluster

> Authored directly by the orchestrator (the routed subagent for this cluster was
> force-downgraded to a tier-2 provider that errored on the `intake` keyword;
> see CLEANUP_PLAN.md "Router" note). Data gathered live 2026-06-16.

## Folder inventory

| Folder / file | Files / lines | Size | Newest mtime | Schema summary | Fresh/stale |
|---|---|---|---|---|---|
| `intake_cycle/` | 11 jsonl + .gitkeep | ~163 KB | 2026-06-16 | daily `cycle_YYYYMMDD.jsonl` rotation | **active** (gaps after Jun 6) |
| `issue_intake/staged_issues.jsonl` | 1 file | **85 MB** | 2026-06-16 10:55 | staged GitHub issues dump | **bloated/abandoned** |
| `issue_intake/latest.json` | 1 file | 73 B | 2026-06-16 15:37 | `{queued_at, records: []}` | active but empty |
| `review_intake/` | 6 files (3 are 0-byte) | ~2 KB | 2026-06-01 | `state.json`, `queue.json`, `findings.jsonl`, 3 empty logs | **stale since Jun 1** |
| `epic_reviews/` | 3 json | ~7 KB | 2026-06-01 | per-epic review snapshots + `latest.json` | stale since Jun 1 |
| `pr_risk/` | 1 (`latest.json`) | 573 B | 2026-06-02 | PR risk score | stale since Jun 2 |
| `queue/` | `.gitkeep` only | 0 B | 2026-06-01 | empty | **dead** |
| `intake_queue.jsonl` (base) | 1317 lines | 479 KB | 2026-06-04 | append-only goal/follow-up queue | **active, never compacted** |

## Strengths

1. **`intake_cycle/` uses correct daily rotation** — `cycle_YYYYMMDD.jsonl` is the one folder in this cluster following a sound retention pattern. Files are bounded per day and human-greppable.
2. **`latest.json` pointer convention** is present in several folders (issue_intake, epic_reviews, pr_risk), giving a stable "current state" read without scanning history.
3. **Lifecycle is captured end-to-end** — items carry `status` transitions (queued → processing → processed/skipped/failed) and link to `bead_id` on closure, so the data *can* support traceability if compacted.

## Weaknesses

1. **`staged_issues.jsonl` is 85 MB while `latest.json` reports `records: []`.** The working state is empty but an 85 MB historical dump is retained in-repo. This is by far the largest single artifact in `07_LOGS_AND_AUDIT/` and the dominant bloat source.
2. **`intake_queue.jsonl` is append-only and never compacted** — 1317 lines for only **248 unique IDs** (5.3× duplication). Status distribution: 534 `queued`, **395 `processing`** (orphaned/stuck — more than the 283 `processed`), 85 `skipped`, 20 `failed`. The high `processing` count means items were claimed and never resolved → the queue cannot be trusted as a work source.
3. **`review_intake/` is an abandoned subsystem** — `state.json` frozen at 2026-06-01, and `dispatch_log.jsonl`, `resolution_log.jsonl`, `reviewer_patterns.jsonl` are all 0 bytes (never written). It looks wired but produces nothing.
4. **`queue/` is completely empty** (`.gitkeep` only) — dead folder masquerading as a subsystem.
5. **Overlapping/redundant queues.** `intake_queue.jsonl`, `intake_cycle/*.jsonl`, `issue_intake/`, `review_intake/queue.json`, and `queue/` all model "work waiting to be processed" in different shapes with no documented authority. A reader cannot tell which is canonical.

## Opportunities

1. **One compaction pass reclaims ~85 MB+** and cuts repo clone/scan time materially.
2. **Define a single canonical intake store** (recommend keeping `intake_queue.jsonl` as the spine, compacted) and demote the rest to derived views or retire them.
3. **Reconcile the 395 stuck `processing` items against `bd`** — many likely correspond to closed/abandoned beads and can be swept to `processed`/`failed`.

## Threats

1. **Orphaned `processing` items** could be re-claimed or skew any "open work" metric, driving bad autopilot decisions.
2. **The 85 MB file in git** inflates every clone and risks tripping GitHub large-file warnings; if it keeps growing it becomes a push hazard.
3. **Silent abandonment** (review_intake, queue) erodes trust — agents may route findings into a dead subsystem and assume they were handled.

## Cleanup Recommendations

| Pri | Action | Rationale | Target |
|---|---|---|---|
| **P0** | Truncate/relocate `staged_issues.jsonl`; if history is needed, gzip to `archive/` outside the repo or git-LFS. Add `*.jsonl` size guard. | 85 MB dead weight; current state already empty. | `issue_intake/` |
| **P0** | Compact `intake_queue.jsonl`: keep only the latest record per `id`, snapshot terminal states to a dated archive, rewrite to 248 lines. | 5.3× duplication; restores trust as a queue. | `intake_queue.jsonl` |
| **P1** | Sweep the 395 `processing` items — cross-check each `id`/`bead_id` against `bd`; mark resolved or `failed` with reason. | Orphaned claims corrupt work-state. | `intake_queue.jsonl` |
| **P1** | Retire `queue/` and the 3 empty `review_intake` logs; if review_intake is intended, document its writer and add a freshness check, else delete the folder. | Dead/abandoned subsystems. | `queue/`, `review_intake/` |
| **P1** | Write an `INTAKE_AUTHORITY.md` declaring the single canonical store and what each other file is (derived/archive/retired). | Five overlapping queues with no documented authority. | cluster root |
| **P2** | Add daily rotation + a 30-day retention prune to whatever still writes `staged_issues.jsonl`; align it with the good `intake_cycle/` pattern. | Prevent re-bloat. | `issue_intake/` |
| **P2** | Investigate the `intake_cycle` gap (Jun 6 → Jun 11 → Jun 16) — is the cycle writer reliably scheduled? | Coverage holes in the one healthy store. | `intake_cycle/` |

## Cross-cluster notes

- **Token/Budget cluster:** the top two `intake_queue.jsonl` items are `token-gov-*` remediation goals — intake feeds the token-governance work tracked there; compaction should preserve those.
- **Session-lifecycle cluster:** `follow_up`/`closure` items reference `CHR-HANDOFF-*` missions and `bead_id`s — the same orphaned-state risk applies to handoff tracking.
- **PDR process (08_PDRS):** intake items carry `bead_id` only *on closure*; the same missing-bead drift seen in the PDR index applies here — queued items reference goal slugs, not real `bd` ids.
- **General structural smell** shared with the Learning/Analytics and Session-lifecycle clusters: many thin/empty/abandoned single-purpose folders. Recommend a repo-wide "freshness + non-empty" audit (see CLEANUP_PLAN.md).
