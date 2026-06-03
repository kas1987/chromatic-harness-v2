# Usage Calibration & Window Tracking — Design Spec

**Date:** 2026-06-03
**Status:** Approved design (pending written-spec review)
**Topic:** Derive real Anthropic usage caps from logged usage vs. native rate-limit percentages; track session→daily→weekly→monthly; surface in the statusline.

---

## 1. Problem & Goal

Claude Code's statusLine hook payload reports usage as **percentages only** —
`rate_limits.five_hour.used_percentage` and `rate_limits.seven_day.used_percentage`
(plus `resets_at` epochs) — never the absolute token ceiling. We don't know how
many tokens we may spend before throttling.

**Primary goal: calibrate the real caps.** Back out the actual ceilings via
`cap = our_usage_in_window ÷ (anthropic_% / 100)`, expressed in a single
**weighted/normalized token** unit, then track and forecast against them.

This is an ongoing calibration: Anthropic changes limits, our weight table
evolves, model mix shifts. The raw snapshot **library is durable and
append-only**, and every calibration run is **versioned and logged** so caps can
be recomputed historically as the method improves.

## 2. Decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Primary purpose | Calibrate the real token caps |
| Calibration unit | Weighted/normalized tokens (`(model,token_type)→weight`, price-based default) |
| Window anchor (reporting) | Fixed **Tuesday 1pm EST → Tuesday 1pm EST** weekly; 5h grid aligned to it |
| Calibration method | **Snapshot-delta** (`Δusage ÷ Δ%` within a window) — anchor-independent |
| Scope | Full: calibration + forecast + rollup + dashboard, built in phases |
| Architecture | **Hybrid** — cheap capture at the `~/.claude` edge; heavy analytics in `chromatic-harness-v2` |

## 3. Architecture & Data Flow

`rate_limits` exists **only** at statusline-render time, but transcript parsing
is expensive — so the edge does cheap appends and the harness does all heavy
compute on its own schedule.

```
EDGE (~/.claude)                       BRIDGE                  HARNESS (chromatic-harness-v2)
─────────────────                      ──────                  ──────────────────────────────
powerline-profile.sh                                           [periodic job]
  ├─ append snapshot ────────►  usage/snapshots.jsonl ───────► H1 ingest: snapshots + transcripts
  │   (Anthropic %s + pointers,  (edge writes, harness reads)      → weighted-token events
  │    no parsing)                                             H2 calibrate: Δtok÷Δ% → calibrated_caps.json
  └─ statusline reads ◄───────  usage/calibrated_caps.json ◄── H3 rollup: session→daily→weekly→monthly
      caps for display          (harness writes, edge reads)   H4 forecast: burn → time-to-limit
                                                               H5 dashboard (09_DEPLOYMENT)
```

- **`snapshots.jsonl`** — the single edge→harness bridge; edge appends only.
- **`calibrated_caps.json`** — the single harness→edge feedback file.
- Harness reconstructs the weighted-token timeline from transcripts referenced in
  snapshots (off the render path), aligns to Anthropic's % at each snapshot ts.
- Edge bridge files in `~/.claude/usage/`; all rollups/history/state in
  `chromatic-harness-v2/07_LOGS_AND_AUDIT/usage_calibration/`.
- Periodic job reuses the existing harness scheduler (Multica autopilot / cron).

## 4. Calibration Algorithm

**Rejected (naive):** `cap = total_usage_in_window ÷ (%/100)` — requires our
window to match Anthropic's rolling window exactly; a fixed anchor biases it.

**Chosen (snapshot-delta):** between two snapshots in the *same* window:

```
cap = Δ(our weighted tokens, t1→t2)  ÷  ((pct_t2 − pct_t1) / 100)
```

Anchor-independent — assumes only that our usage and Anthropic's % move together
within a window. One estimate per valid snapshot pair, aggregated by **median**.

**Edge cases:**
- Reset between snapshots (`pct` drops or `resets_at` changed) → discard pair, start fresh segment.
- `Δpct ≈ 0` (idle / coarse %) → discard (avoid divide-by-tiny).
- Model switch mid-window → weighted unit normalizes across models; tag estimates by
  model-mix to later separate **weekly all-models** vs **Sonnet-only** tracks.
- Weight-table uncertainty → same weights scale both Δusage and the cap; pin to current
  pricing, store `weight_table_version` with each calibration.
- Cold start → until ≥5 valid pairs per window type, mark cap **provisional**; statusline falls back to raw `%`.

## 5. Data Formats, Library & Retention

**`~/.claude/usage/snapshots.jsonl`** (edge-appended, durable library, never auto-deleted):
```json
{"ts":1780526400,"session_id":"…","model":"claude-opus-4-8",
 "five_hour":{"pct":8.0,"resets_at":1780544400},
 "seven_day":{"pct":16.0,"resets_at":1781024400},
 "context_window":{"input":188762,"output":1428,"used_pct":19},
 "cost":{"total_cost_usd":9.75,"total_duration_ms":2900599},
 "transcript_path":"…","schema":1}
```
- Edge keeps a rolling tail (≈30 days / size-capped) for liveness; harness ingests
  **every** line into permanent `07_LOGS_AND_AUDIT/usage_calibration/snapshots_archive.jsonl`
  (+ dated rotations). Nothing is lost — this is the library we dial against.

**Weighted-token events** — `usage_calibration/wtok_events.jsonl`:
```json
{"ts":…,"session_id":"…","model":"…","request_id":"…",
 "raw":{"input":…,"output":…,"cache_creation":…,"cache_read":…},
 "wtok":12873,"weight_table_version":"2026-06-pricing"}
```
Deduped by `request_id` (reuse `usage-tracker.sh` logic). `wtok` recomputable from `raw` + weight version.

**Weight table** — `usage_calibration/weight_table.json` (versioned):
```json
{"version":"2026-06-pricing","reference":"sonnet-input",
 "weights":{"claude-opus-4-8":{"input":5.0,"output":25.0,"cache_creation":6.25,"cache_read":0.5}}}
```

**Calibration history** — `usage_calibration/calibration_history.jsonl` (append-only, one entry/run):
stamps `cap_wtok`, `n_estimates`, `spread`, `weight_table_version`, `epoch_id`. A
**regime-change detector** opens a new **epoch** on a sustained cap shift beyond the
spread band (re-baseline rather than blend stale data). `calibrated_caps.json` reflects the current epoch:
```json
{"updated_at":"…","weight_table_version":"2026-06-pricing","epoch_id":"e3",
 "five_hour":{"cap_wtok":512000,"confidence":"ok","n_estimates":23,"spread_pct":8},
 "seven_day":{"cap_wtok":4100000,"confidence":"prov","n_estimates":4,"spread_pct":31},
 "seven_day_sonnet":{"cap_wtok":null,"confidence":"none"}}
```

**Recompute-from-library** — `recalibrate --from <date> --weights <version>` rebuilds caps
historically from raw snapshots + raw token events whenever weights/method improve.

## 6. Rollup, Forecast, Dashboard

- **Rollup** (`usage_calibration/rollup.json`) — buckets `wtok_events` into
  session → daily → weekly (**Tue 1pm EST → Tue 1pm EST**, computed in
  `America/New_York` for DST) → monthly. Each bucket: `wtok`, `usd`, `pct_of_cap`.
- **Forecast** (`usage_calibration/forecast.json`) — trailing burn slope (wtok/hr) ÷
  remaining-to-cap → time-to-limit per window + a "safe burn to coast to reset" figure.
  Reuses `budget_forecast_snapshot.py` patterns.
- **Dashboard** — extends `09_DEPLOYMENT/dashboards`: calibration confidence over time,
  epoch timeline, window utilization, burn vs. time-to-reset, monthly trend.

## 7. Statusline Integration

Cleanup applied: drop the `⬡ risk/gov` env segment and both `$` segments; aligned
4-column grid; last column is the flexible/extending one.

```
Row 1:  ✱ model  │  repo  │  ▓▓▓░░░░░░░ context (bar only)  │  5h 8% · 41k/512k ·2h
Row 2:  ⧗ boot   │  ⚡ wk 16% ·5d        │  ⟼ ~3d to cap     │  § 660k/4.1M · $9.75
```

- **Context bar (Row 1 Col 3)** fills the column, **bar only, no text**. Color by
  **% of the applicable model's context window** (Sonnet/Haiku 200k, Opus 1M):
  **yellow ≥ 55%, red ≥ 70%**. Requires a context-segment fork patch (see §8).
- Freed slots carry the payoff: real token counts vs. derived caps, forecast, and cost
  (token + $ together in the last cell). Exact cell assignment tunable in implementation.
- Provisional caps → cells gracefully show raw `%` only.

## 8. Required `claude-powerline` fork patches (we own the repo)

1. **Done already:** `git` segment honors `showBranch:false`/`showStatus:false` (repo-name-only).
2. **Context thresholds** — `src/segments/context.ts` hardcodes `LOW:50, MEDIUM:80`;
   change to **55 / 70**, ideally config-driven; ensure color uses the **raw
   model-relative percentage** (tokens ÷ model window), not the autocompact-buffered value.
3. **Model context limits** — set `modelContextLimits = {sonnet:200000, opus:1000000, default:200000}`.
4. **Bar-only context** — add a toggle to hide the numeric/label text so Col 3 is pure bar.

Rebuild `dist/` via `npm run build` after patches.

## 9. Phasing

- **P1 — Calibration foundation:** edge snapshot appender → harness ingest →
  weighted-token events → delta-calibration → `calibrated_caps.json` → statusline
  shows real caps. *(v1 that unblocks everything.)*
- **P2 — Library & epochs:** durable archive, calibration_history, regime detection, `recalibrate` tool.
- **P3 — Rollup + forecast:** session→daily→weekly→monthly + time-to-limit.
- **P4 — Dashboard:** the visual layer.

## 10. Error Handling & Testing

**Error handling:**
- Every JSON read wrapped in try/except (partial-write tolerant — global rule).
- Edge appender must never block/break the statusline: any failure → silent skip, statusline still renders.
- Harness jobs idempotent: safe to re-run; dedup by `request_id` + snapshot `ts`.

**Testing:**
- Unit: weighting math; delta-calibration incl. reset/idle/model-switch edge cases;
  Tue-1pm-EST bucketing across DST.
- Golden-file: recorded `snapshots.jsonl` + transcript → assert derived cap.
- Idempotency: re-run ⇒ identical output.

## 11. Open Items / Future

- Confirm a "Sonnet-only" weekly track is derivable (native payload currently exposes only
  `five_hour` + `seven_day`; Sonnet-only % seen in the UI panel may not reach the hook —
  verify from captured payloads, else derive from model-tagged rollup).
- "Extra usage $X of $50" field not present in the hook payload; source TBD.
- claude-powerline repo still on `Owloops` remote (READ-only); rehome pending (see estate consolidation).
