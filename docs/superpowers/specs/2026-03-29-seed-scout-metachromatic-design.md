# Seed Scout + Seed Library — Design Spec
**Date:** 2026-03-29
**Status:** Approved
**Scope:** Metachromatic integration of seed scouting, scoring, and library

---

## 1. Goal

Give the generation pipeline a first-class UI for:
1. Launching low-res scout batches against ComfyUI for any character/checkpoint/act
2. Scoring results (S+/S/A/B/F) with one click — in real-time during generation or after the fact
3. Browsing the scored seed library, promoting winners to gold, launching variant scouts

All wired into the existing Metachromatic app under the `/ai-training` hub.

---

## 2. Architecture Overview

```
Metachromatic (Electron + React)
├── /ai-training/seed-scout     ← new: batch launcher
├── /ai-training/seed-library   ← new: full grid + lightbox scorer
└── /review                     ← existing: smoke_decor, extended to write seed scores

seed_api.py (FastAPI, port 9883)    ← new: single Python backend for both UIs
├── GET  /seeds                     ← query generation_seeds from models.db
├── GET  /img/:filename             ← serve scout images from .01_OUT
├── POST /score                     ← write/update score in generation_seeds
├── POST /scout                     ← queue ComfyUI scout batch
└── GET  /queue-status              ← SSE: live ComfyUI job progress

smoke_decor_live_server.py (port 9881)
└── extended: POST /score now calls seed_api POST /score when
    filename matches scout_ prefix → both UIs share one write path

models.db (D:\.000_AI\models.db)
└── generation_seeds table (created by 05_seed_tracker.py)
```

**Electron IPC:** `seed-api-start` / `seed-api-stop` handlers in main process, matching the existing smoke_decor IPC pattern. `seed_api.py` starts on app launch alongside smoke_decor.

---

## 3. Filename Convention

All scout batch outputs follow this naming pattern (enforced by `seed_api.py` when queuing):

```
scout_{slug}_{checkpoint}_{act}_s{seed}_{batch_idx:05d}_.png
```

Example: `scout_emily_willis_PR23_solo_standing_s1042_00001_.png`

Both `seed_api.py` and `smoke_decor_live_server.py` parse this pattern to auto-populate `model_slug`, `checkpoint`, `act`, and `seed` when writing scores — no manual entry.

---

## 4. Python API Server (`seed_api.py`)

**Location:** `D:/.04_Prism/scripts/lora_pipeline/seed_api.py`
**Port:** 9883
**Runtime:** `D:/.04_Prism/.venv/Scripts/python.exe`
**Dependencies:** `fastapi`, `uvicorn`, `sqlite3` (stdlib)

**Schema addition:** `05_seed_tracker.py` schema gains one column before first use:
```sql
ALTER TABLE generation_seeds ADD COLUMN gold INTEGER DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_seeds_gold ON generation_seeds(gold) WHERE gold = 1;
```
`seed_api.py` runs this migration on startup (idempotent — catches `duplicate column` and continues).

### Endpoints

#### `GET /characters`
Returns all model slugs eligible for scouting (from `models.db`).

```
Query params:
  q           string   — search filter on model_slug / model_name
  limit       int      — default 200

Response: [{slug, model_name, ethnicity, aurora_archetype, total_images}, ...]
```

Used to populate the character selector in Seed Scout.

#### `GET /seeds`
Query `generation_seeds` with filters.

```
Query params:
  slug        string   — filter by model_slug
  checkpoint  string   — PR23 | CRP | PMP | BSY_XL
  act         string   — optional act filter
  min_score   string   — S+ | S | A | B | C | F
  unscored    bool     — include rows with score IS NULL
  limit       int      — default 100

Response: [{seed_id, model_slug, checkpoint, act, seed, score,
            composite_score, notes, image_path, logged_at}, ...]
```

#### `GET /img/:filename`
Stream image file from `D:\.000_AI\.01_OUT\{filename}`. Returns 404 if not found.

#### `POST /score`
Upsert a score. If `seed_id` is provided, updates that row. Otherwise inserts (or updates by slug+checkpoint+seed uniqueness).

```json
{
  "seed_id": 42,           // optional — update existing row
  "model_slug": "emily_willis",
  "checkpoint": "PR23",
  "act": "solo_standing",
  "seed": 1042,
  "score": "S+",
  "composite_score": 91.5,
  "notes": "great sag, clean face",
  "image_path": "scout_emily_willis_PR23_solo_standing_s1042_00001_.png"
}
```

Returns: `{seed_id, updated: true}`

#### `POST /scout`
Queue a scout batch to ComfyUI. Builds the workflow JSON using Phase 1 scout settings and posts each seed as a separate job.

```json
{
  "slug": "emily_willis",
  "checkpoint": "PR23",
  "act": "solo_standing",
  "seed_start": 1000,
  "seed_count": 50,
  "width": 768,
  "height": 512,
  "steps": 12,
  "cfg": 6.0,
  "batch_size": 8
}
```

Returns: `{queued: 47, skipped_tested: 3, job_ids: [...]}`
(Already-tested seeds from `generation_seeds` are skipped.)

#### `GET /queue-status` (SSE)
Server-Sent Events stream of ComfyUI queue state.

```
data: {"status": "running", "current_seed": 1023, "completed": 23, "total": 47}
data: {"status": "idle"}
```

Polls ComfyUI `GET /queue` every 2 seconds.

---

## 5. React Routes

### `/ai-training/seed-scout`

**Component:** `SeedScoutMode.tsx`

**Layout:**
```
┌─────────────────────────────────────────┐
│  Character selector (searchable)        │
│  Checkpoint selector  Act selector      │
│  Seed range: [start] → [end]            │
│  Scout settings: Res / Steps / CFG / Batch │
│  ──────────────────────────────────     │
│  Untested in range: 47 / 50  (from DB)  │
│  [▶ Queue Scout Batch]                  │
│  ──────────────────────────────────     │
│  ComfyUI queue: ● Running seed 1023/50  │
│  [→ Go to Seed Library]                 │
└─────────────────────────────────────────┘
```

**Behaviour:**
- Character list populated from `models.db` via `seed_api GET /seeds` (distinct slugs) or a separate `GET /characters` endpoint
- Untested count: `GET /seeds?slug=X&checkpoint=Y&act=Z` — seeds in range not yet in DB
- Scout settings pre-filled with Phase 1 defaults (768×512, 12 steps, CFG 6.0, batch 8)
- Queue button: `POST /scout` → shows SSE progress from `GET /queue-status`
- "Go to Seed Library" button navigates to `/ai-training/seed-library?slug=X&checkpoint=Y`

### `/ai-training/seed-library`

**Component:** `SeedLibraryMode.tsx`

**Layout:**
```
┌─ Filter bar ──────────────────────────────────────────┐
│  [slug ▾]  [checkpoint ▾]  [act ▾]  [score ▾]  [8 unscored] │
├─ Image grid (6 cols, fills viewport) ─────────────────┤
│  [img] S+   [img] S   [img] A   [img] A   [img] ●   [img] ● │
│  [img] B    [img] F   [img] ●   ...                          │
└───────────────────────────────────────────────────────┘
```

- **Unscored badge:** amber highlight + "rate me" label on images with no score in DB
- **Score border colour:** S+=green, S=teal, A=blue, B=grey, F=red, unscored=amber

**Lightbox (click any image):**
```
┌─ Lightbox overlay ────────────────────────────────────┐
│  [← prev]   [full image]   [next →]                   │
│                                                        │
│  seed 1042 · PR23 · solo_standing · emily_willis       │
│  [S+] [S] [A] [B] [C] [F]   ← click to score/update  │
│  Notes: [___________________________]                  │
│  [★ Promote to Gold]  [▶ Scout Variants from seed]    │
│                                            [✕ Close]  │
└───────────────────────────────────────────────────────┘
```

**Behaviour:**
- Scores write immediately on grade click: `POST /score` — no save button
- Rescoring an existing seed: same endpoint, `seed_id` passed → updates existing row
- "Promote to Gold": writes to `gold-seeds-database.md` pattern + sets a `gold` flag on the row
- "Scout Variants": pre-fills Seed Scout form with this seed as start+1, opens `/ai-training/seed-scout`
- Images served via `seed_api GET /img/:filename`

---

## 6. smoke_decor Extension

`smoke_decor_live_server.py` gets one new behaviour: when it processes a score for an image whose filename matches `scout_*`, it additionally POSTs to `seed_api` at `http://127.0.0.1:9883/score` with the parsed slug/checkpoint/act/seed context.

This is a fire-and-forget POST. If `seed_api` is not running, the error is logged and ignored — smoke_decor continues working normally.

No change to smoke_decor's existing CSV output or SSE behaviour.

---

## 7. Navigation

Add two tabs to `UnifiedAITrainingHub`'s tab bar:

```
Training | ComfyUI | Seed Scout | Seed Library | Pipeline
```

`Seed Scout` and `Seed Library` sit between `ComfyUI` and `Pipeline`.

---

## 8. Electron IPC

Add to `main.ts` (alongside existing smoke-decor handlers):

```typescript
ipcMain.handle('seed-api-start', async () => {
  // spawn .venv/Scripts/python.exe scripts/lora_pipeline/seed_api.py
  // return { port: 9883 }
})

ipcMain.handle('seed-api-stop', async () => {
  // kill the process
})
```

`seed_api.py` starts on app launch in `App.tsx` via `useEffect` (same pattern as smoke_decor).

---

## 9. Data Flow Summary

```
User clicks "Queue Scout Batch"
  → React POST /scout → seed_api.py
  → seed_api queries generation_seeds to skip tested seeds
  → seed_api POSTs workflow JSONs to ComfyUI :8188 (one per seed)
  → ComfyUI generates → saves to D:\.000_AI\.01_OUT\scout_*.png
  → SSE /queue-status feeds progress back to React

Images land in .01_OUT
  → Option 1: /review tab (smoke_decor) picks them up via SSE file watcher
    → User grades → smoke_decor POSTs to seed_api /score
  → Option 2: User navigates to /ai-training/seed-library
    → Images loaded via seed_api GET /img/:filename
    → Grid shows unscored amber highlights
    → User clicks image → lightbox → grades → POST /score

Scores persist in generation_seeds (models.db)
  → Seed Library always reflects current DB state
  → 05_seed_tracker.py CLI remains usable for scripted logging
```

---

## 10. Files Created / Modified

| File | Status | Description |
|---|---|---|
| `scripts/lora_pipeline/seed_api.py` | **New** | FastAPI server, port 9883 |
| `scripts/lora_pipeline/05_seed_tracker.py` | Exists | CLI stays unchanged |
| `Image-Prism/apps/metachromatic/src/features/SeedScoutMode.tsx` | **New** | React scout launcher |
| `Image-Prism/apps/metachromatic/src/features/SeedLibraryMode.tsx` | **New** | React grid + lightbox |
| `Image-Prism/apps/metachromatic/src/routes.tsx` | **Modify** | Add 2 routes |
| `Image-Prism/apps/metachromatic/src/features/UnifiedAITrainingHub.tsx` | **Modify** | Add 2 tabs |
| `Image-Prism/apps/metachromatic/src/main.ts` | **Modify** | IPC handlers for seed-api |
| `Image-Prism/apps/metachromatic/src/App.tsx` | **Modify** | Start seed_api on launch |
| `scripts/review/smoke_decor_live_server.py` | **Modify** | Forward scout scores to seed_api |

---

## 11. Out of Scope

- LoRA training trigger from Seed Library (future: "Train on top seeds" button)
- Multi-character comparison grid across seed library
- Seed sharing / export to other projects
- Mobile / non-Electron web access
