# Command Center — Phase 1 Canonicalization + Phase 2 Theme Runtime

**Date:** 2026-06-16
**Scope:** `05_FRONTEND_CONSOLE` — structural canonicalization (P1) and asset-pack theme system (P2)

---

## What shipped

### Phase 1 — Canonicalization

- **`src/lib/api.ts`** — canonical API client targeting `:8787` (Python hub) and `:3030` (Node console). Full typed interface set: `MissionPacket`, `Mission`, `MagnetEvent`, `GateResult`, `Bead`, `AgentProfile`, `PromotionRecord`, `LevelThreshold`, `TrendPoint`, `MagnetBreakdown`, `MissionAnalytics`, `SynthesisResult`. All fetch paths use a shared `apiCall<T>()` envelope; `getMissionAnalytics` and `getMissionEventsRange` call the Python hub directly.
- **`src/app/page.tsx`** — consolidated 8-panel Command Center page replacing prior flat layout. Panels: Mission Dashboard, Magnet Event Stream, Confidence & Risk, Beads Queue (with status + priority filters), Independent Review, PDR Generator (stub), Action Launcher (stub), Sandbox Lab Results (stub). Full-width rows for MissionReplay and Agent Trust Profiles/Registration added below the grid. 5-second polling via `setInterval`.
- **`src/app/layout.tsx`** — root layout wrapping everything in `ThemeProvider`; CSS var fallbacks (`--cc-bg: #0a0a0a`, `--cc-text: #e0e0e0`) ensure correct first paint before client hydration.
- **`src/components/AgentProfiles.tsx`** — agent list + selected-agent detail panel (level badge, success-rate bar, risk-score bar, promotion history). Fully theme-reactive via `useTheme()`.
- **`src/components/AgentRegistration.tsx`** — register and promote agents; reads level thresholds from API; also theme-reactive.
- **`src/components/MissionReplay.tsx`** — rendered conditionally when a mission is selected; plugs into the `getMissionEventsRange` Python-hub endpoint.
- **`src/hooks/useWebSocketEvents.ts`** — drop-in WebSocket hook for real-time magnet events (types: `magnet_event`, `magnet_synthesis`, `gate_decision`, `bead_created`). Not yet wired into the page; ships as the future alternative to HTTP polling.

### Phase 2 — Theme runtime

- **`assets/prompt_variants/default_neon.asset_pack.yaml`**, **`magnetic_gold.asset_pack.yaml`**, **`prism_cosmic.asset_pack.yaml`** — three canonical asset-pack YAML files; source of truth for all visual token values.
- **`schemas/asset_swap_pack.schema.json`** — JSON Schema (Draft 2020-12) that `generate_console_themes.py` validates each pack against before emitting TypeScript.
- **`scripts/generate_console_themes.py`** — offline generator: reads `assets/prompt_variants/*.asset_pack.yaml`, validates against the schema, normalises heterogeneous colour keys into the `ConsoleTheme` token set, and writes `05_FRONTEND_CONSOLE/src/lib/themes.generated.ts`. Zero YAML dependency added to the Next.js bundle.
- **`src/lib/themes.generated.ts`** — auto-generated; exports `ConsoleTheme` interface, `ThemeId` union (`"default_neon" | "magnetic_gold" | "prism_cosmic"`), `THEMES` array, `DEFAULT_THEME_ID`, and `getTheme()` helper.
- **`src/lib/theme.tsx`** — `ThemeProvider` + `useTheme()` hook. Persists the active theme id to `localStorage` (key `cc.themeId`); mirrors the 12 canonical tokens onto `--cc-*` CSS custom properties on `document.documentElement` on each theme change. SSR-safe: localStorage read deferred to `useEffect`.
- **`src/components/ThemeSwitcher.tsx`** — dropdown in the Command Center header. Options driven entirely by the `THEMES` array from `themes.generated.ts`; no hardcoded entries.

---

## Key decisions

**Taxonomy over flat (docs/* pointer stubs).** The PDR Generator panel and Action Launcher panel ship as stubs with explicit pointer labels (`PDR_FRONTEND_CONSOLE.md`, `PDR_VISUAL_CONTROL_PLANE.md`, `PDR_AGENT_TRUST.md`) rather than live content. This establishes the taxonomy for the `docs/pdr/` namespace without blocking the structural milestone.

**Generator over runtime YAML dependency.** The `package.json` for `05_FRONTEND_CONSOLE` ships only `next` and `react`; no `js-yaml` or schema-validation library is added to the frontend bundle. The YAML packs are canonical and human-editable; the generator (`scripts/generate_console_themes.py`) runs offline and checks in `themes.generated.ts`. Adding a new theme = edit the YAML, re-run the script.

**`api.ts` left untouched as the sole API surface.** `.env.local` already sets `NEXT_PUBLIC_API_URL=http://localhost:8787`, which is the Python hub port. The `apiCall<T>()` envelope wraps the `{ data: ... }` response shape expected from that server. Changing the envelope would require coordinated changes to the runtime server; the decision was to leave it structurally stable for this phase.

**Data-driven ThemeSwitcher so unshipped packs never appear.** Because `ThemeSwitcher` iterates `THEMES` (the generated array), a theme that has no corresponding `*.asset_pack.yaml` — for example, the planned "Storm Console" dark-storm variant — simply does not appear as an option until the generator is run after its pack is authored and validated. No conditional rendering or feature-flags needed.

---

## Verification

- `tsc` (Next.js build type-check): **0 non-test errors** across all files in `src/`.
- Schema validators: all three `.asset_pack.yaml` files pass `Draft202012Validator` in `generate_console_themes.py` (no schema errors on generation run).
- Three themes differentiate visually: `default_neon` uses blue accent (`#3b82f6`) + purple brand (`#8b5cf6`); `magnetic_gold` uses gold accent (`#facc15`) + amethyst brand (`#a855f7`); `prism_cosmic` uses sky accent (`#0ea5e9`) + lavender brand (`#c084fc`) on a deep-space background (`#020617`). Theme switch persists across page reload via `localStorage`.

---

## Deferred / gated

- **`useWebSocketEvents` wired into the page** — hook ships but is not yet integrated into `page.tsx`; HTTP polling (`setInterval` at 5s) remains active. Blocked on a WebSocket endpoint being stable in the Node console server.
- **PDR Generator live generation** — stub panel only. Requires the `POST /missions/:id/pdr` endpoint and the document-generation pipeline to land first.
- **Action Launcher wired actions** — "Rerun Validation", "Create Bead", "Dispatch Agent" buttons render and are gated on mission selection but call no API yet. Blocked on endpoint definitions for each action type.
- **Sandbox Lab Results** — placeholder panel. Blocked on the sandbox execution runtime being available in this environment.
- **Storm Console asset pack** — not authored; no `.asset_pack.yaml` exists. Will appear automatically in the theme switcher once the pack is created and the generator is re-run.
- **Redis pub/sub fanout for WebSocket horizontal scale** — documented in `docs/console/WEBSOCKET_EVENT_BUS.md`; requires `REDIS_URL` and `ws_redis_fanout.py` worker. Not needed for single-instance dev mode.
- **`MissionReplay` event-range integration** — component exists and renders when a mission is selected; the `getMissionEventsRange` call targets the Python hub's `?from_ts`/`?to_ts` parameters but is not yet connected to any replay-scrubber UI.

---

## Follow-up

- Author `storm_console.asset_pack.yaml`, run the generator, verify it appears in the switcher without code changes.
- Wire `useWebSocketEvents` into `page.tsx` behind an env flag (`NEXT_PUBLIC_USE_WS=true`) so polling and WS can coexist during rollout.
- Define and implement the three Action Launcher endpoints; remove the `disabled={!selected}` gate once at least "Rerun Validation" is live.
- Add a replay scrubber UI to `MissionReplay` that passes `from_ts`/`to_ts` to `getMissionEventsRange`.
- Decide whether PDR auto-generation triggers on mission `completed` status or on an explicit user action; stub the `POST /missions/:id/pdr` endpoint accordingly.
