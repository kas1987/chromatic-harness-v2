# Seed Scout + Character Profiles Redesign
**Date:** 2026-03-29
**Status:** Design Approved
**Scope:** UI/UX simplification + archetype-driven recommendations + preset persistence

---

## 1. Goal

Redesign Seed Scout to be **friendly and simplified** by:
1. Connecting character selection to Hero/Archetype profiles
2. Auto-generating recommended settings (checkpoint, act, seed range) from archetype data
3. Showing a full customization panel with all generation settings
4. Persisting presets per character for quick repeat scouts

**Success criteria:**
- User selects character → sees smart recommendations → optionally customizes → runs scout
- Presets save to character JSON and auto-load next time
- All profile context (warm lighting rules, body calibration, etc.) visible in recommendations

---

## 2. Architecture Overview

### 2.1 Data Flow

```
Character Selection (archetype + model)
  ↓
Load Archetype Profile (.agents/character_profiles/{ethnicity}_archetype.json)
Load Character Profile (.agents/character_profiles/full/{name}_full.json)
  ↓
Generate Recommendations:
  • Checkpoint: from archetype.scout_preset.checkpoint
  • Act: from archetype.scout_preset.act
  • Seed Range: from archetype.scout_preset.seed_range
  • Generation settings: Phase 1 defaults
  ↓
Display Recommendation Panel
  • Show recommended settings with checkmarks
  • Show profile notes (warm lighting, body calibration, etc.)
  • Offer "Save as Preset" checkbox
  ↓
Optional: Customize Drawer
  • Edit any setting (checkpoint, act, seed range, steps, CFG, batch, resolution)
  • Save customizations as preset for this character
  ↓
Run Scout Batch via seed_api /scout endpoint
  • Presets save to {name}_full.json after "Save as Preset" accepted
```

### 2.2 File Structure

**Archetype profiles** — new `scout_preset` block:
```json
{
  "profile_id": "ukrainian_archetype",
  "display_name": "Ukrainian",
  "linked_ethnicity": "ukrainian",
  // ... existing fields ...
  "scout_preset": {
    "checkpoint": "CRP",
    "act": "editorial",
    "seed_range": { "start": 1000, "count": 50 },
    "generation_settings": {
      "steps": 12,
      "cfg": 6.0,
      "batch_size": 8,
      "width": 768,
      "height": 512
    }
  }
}
```

**Character profiles** — new `scout_preset` block (overrides archetype):
```json
{
  "profile_id": "mila_azul",
  "display_name": "Mila Azul",
  "linked_archetype": "ukrainian_archetype",
  // ... existing fields ...
  "scout_preset": {
    "checkpoint": "CRP",
    "act": "editorial",
    "seed_range": { "start": 1000, "count": 50 },
    "generation_settings": {
      "steps": 12,
      "cfg": 6.0,
      "batch_size": 8,
      "width": 768,
      "height": 512
    },
    "last_used": "2026-03-29T14:23:00Z"
  }
}
```

---

## 3. Seed Scout Component Structure

### 3.1 SeedScoutMode (main container)

**State:**
- `step`: 'character' | 'recommendations' | 'customize' | 'running'
- `selectedCharacter`: { slug, name, archetype, tier, images }
- `archetypeProfile`: loaded archetype JSON
- `characterProfile`: loaded character JSON
- `recommendedSettings`: computed from archetype
- `customizedSettings`: user edits (only if customizing)
- `isScouting`: boolean
- `scoutProgress`: { current_seed, completed, total }

**Routes & Renders:**
- Step 1: `<SeedScoutCharacterSelector />`
- Step 2: `<SeedScoutRecommendations />`
- Step 3: `<SeedScoutCustomize />` (optional)
- Step 4: `<SeedScoutRunning />`

### 3.2 SeedScoutCharacterSelector

**Input:**
- Search query (filters by slug/name)
- Archetype groups (Ukrainian, Russian, Lebanese, Persian, etc.)
- Models within each archetype

**Behavior:**
- Display archetypes as expandable groups
- Show model names + image counts
- Single-select via radio button
- "Next" button disabled until character selected

**Output:**
- `{ slug, name, archetype, tier, images }`

### 3.3 SeedScoutRecommendations

**Input:**
- `characterProfile`: loaded from JSON
- `archetypeProfile`: loaded from JSON
- `recommendedSettings`: computed (archetype defaults)

**Display:**
- Recommended checkpoint (with explanation)
- Recommended act (with explanation)
- Recommended seed range (with explanation)
- Generation settings (Phase 1 defaults, read-only)
- Profile notes (warm lighting, body calibration, etc.)
- "Save as Preset" checkbox (checked by default)
- Buttons: [← Change Character] [Customize ▼] [Run Scout ▶]

**Behavior:**
- Click "Customize ▼" → slide in drawer or navigate to Step 3
- Click "Run Scout ▶" → accept current recommendations, optionally save preset, go to Step 4
- Click "← Change Character" → back to Step 1

### 3.4 SeedScoutCustomize

**Input:**
- All fields editable (checkpoint, act, seed range, steps, CFG, batch, resolution)
- "Save as Preset" checkbox

**Behavior:**
- Checkpoint: dropdown (CRP | PR23 | Uber | PMP)
- Act: dropdown of known acts + free-form text input option
- Seed range: two inputs (start, count)
- Generation settings: numeric inputs with sensible ranges
- "Save as Preset" persists settings to character JSON
- [Back] → Step 2 | [Run Scout] → Step 4

### 3.5 SeedScoutRunning

**Input:**
- Progress from SSE `/queue-status`
- `{ status, current_seed, completed, total }`

**Display:**
- Scout metadata (character, checkpoint, act, seed range)
- Progress bar (% complete)
- Current seed / total seeds
- Est. time remaining
- Output path (`D:\.000_AI\.01_OUT\scout_*_*.png`)

**Buttons:**
- [Cancel Scout] → abort batch, back to recommendations
- [View Seed Library ▶] → navigate to `/ai-training/seed-library`

---

## 4. Preset Persistence

### 4.1 Preset Schema

Archetype presets (baked in, never modified):
```json
{
  "scout_preset": {
    "checkpoint": "CRP",
    "act": "editorial",
    "seed_range": { "start": 1000, "count": 50 },
    "generation_settings": { "steps": 12, "cfg": 6.0, ... }
  }
}
```

Character presets (user-editable, optional):
```json
{
  "scout_preset": {
    "checkpoint": "CRP",
    "act": "editorial",
    "seed_range": { "start": 1000, "count": 50 },
    "generation_settings": { "steps": 12, "cfg": 6.0, ... },
    "last_used": "2026-03-29T14:23:00Z"
  }
}
```

### 4.2 Load Order

1. Load archetype profile → `scout_preset` becomes defaults
2. Load character profile → if `scout_preset` exists, override archetype defaults
3. Display recommendations from merged preset
4. If user saves customizations → write new `scout_preset` to character JSON

### 4.3 Write Behavior

When user clicks "Save as Preset" in customize drawer:
- Merge current settings into character profile JSON
- Write to `.agents/character_profiles/full/{name}_full.json`
- Set `last_used` timestamp
- Reload character picker (optional: highlight recently-used)

---

## 5. Recommendations Logic

### 5.1 Checkpoint Selection

**Rule:** Load from `archetype.scout_preset.checkpoint`

Examples:
- Ukrainian, Russian, Nordic → CRP (ethnicity fidelity, fair-skin)
- Nigerian, Ethiopian → CRP (skin tone fidelity)
- Lebanese, Persian → CRP or Uber (CRP for ethnicity, Uber for body)
- L8 characters → Uber (body/fluid quality over ethnicity)

### 5.2 Act Selection

**Rule:** Load from `archetype.scout_preset.act`

Examples:
- Fair-skin characters → "editorial" (S+ tier)
- L8 explicit → "explicit_bust", "blowjob", etc.
- General → "solo_standing"

### 5.3 Seed Range Selection

**Rule:** Load from `archetype.scout_preset.seed_range`

Standard ranges:
- L1–L4 (Elite tier) → 1000–1050
- L5–L7 → 2000–2050
- L8 (Explicit) → 3000–3050

### 5.4 Generation Settings

**Phase 1 defaults** (all archetypes, all levels):
- Steps: 12
- CFG: 6.0
- Batch size: 8
- Resolution: 768×512

These are Phase 1 scout defaults and not archetype-specific.

---

## 6. seed_api Changes

### 6.1 New Endpoint: `/recommend`

```
GET /recommend?slug={slug}&use_character_preset={bool}

Query params:
  slug                   string   — model slug (required)
  use_character_preset   bool     — prefer character preset over archetype (default: true)

Response:
{
  "ok": true,
  "archetype": "ukrainian_archetype",
  "archetype_display": "Ukrainian",
  "checkpoint": "CRP",
  "act": "editorial",
  "seed_range": { "start": 1000, "count": 50 },
  "generation_settings": { "steps": 12, "cfg": 6.0, "batch_size": 8, "width": 768, "height": 512 },
  "profile_notes": [
    "Warm lighting mandatory: cool platinum blonde requires golden hour rays",
    "Body calibration: sag 1.5, ptosis 1.4, heavy droop",
    "Secondary anchor: blue eyes paired with angular face"
  ]
}
```

**Logic:**
1. Query `models.db` for `ethnicity`, `aurora_archetype` where `model_slug = ?`
2. Load archetype profile JSON from `.agents/character_profiles/{ethnicity}_archetype.json`
3. If `use_character_preset=true`, attempt to load `.agents/character_profiles/full/{slug}_full.json`
4. Merge: character preset overrides archetype preset
5. Return merged recommendations + profile notes from archetype

### 6.2 Existing `/scout` Endpoint

No change to signature, but now receives preset data from React component (already validated by `/recommend`).

### 6.3 Existing `/score` Endpoint

No change (seed scoring already works).

---

## 7. React Integration

### 7.1 New Files

```
src/features/SeedScoutMode/
├── SeedScoutMode.tsx              (main container, step state machine)
├── SeedScoutCharacterSelector.tsx (step 1)
├── SeedScoutRecommendations.tsx   (step 2)
├── SeedScoutCustomize.tsx         (step 3)
├── SeedScoutRunning.tsx           (step 4)
├── useSeedScoutStore.ts           (Zustand store for state)
└── seed-scout.css                 (styling)
```

### 7.2 Zustand Store: `useSeedScoutStore`

```typescript
interface SeedScoutState {
  // Current step
  step: 'character' | 'recommendations' | 'customize' | 'running';

  // Character selection
  selectedCharacter: { slug: string; name: string; archetype: string; tier: string; images: number } | null;

  // Loaded profiles
  archetypeProfile: any;
  characterProfile: any;

  // Recommendations (from /recommend endpoint)
  recommendedSettings: {
    checkpoint: string;
    act: string;
    seed_range: { start: number; count: number };
    generation_settings: { steps: number; cfg: number; batch_size: number; width: number; height: number };
    profile_notes: string[];
  };

  // Customizations (if user edits in Step 3)
  customizedSettings: Partial<recommendedSettings>;
  shouldSavePreset: boolean;

  // Scout progress
  isScouting: boolean;
  scoutProgress: { current_seed: number; completed: number; total: number } | null;

  // Actions
  setStep: (step: string) => void;
  selectCharacter: (character: any) => void;
  loadRecommendations: (slug: string) => Promise<void>;
  updateCustomizedSettings: (settings: Partial<recommendedSettings>) => void;
  setShouldSavePreset: (shouldSave: boolean) => void;
  startScout: () => Promise<void>;
  updateScoutProgress: (progress: any) => void;
  cancelScout: () => void;
}
```

### 7.3 Route Addition

In `src/routes.tsx`:
```typescript
{
  path: '/ai-training/seed-scout',
  component: <SeedScoutMode />
}
```

In `UnifiedAITrainingHub` tabs:
```
[Training] [ComfyUI] [Seed Scout] ← NEW [Seed Library] [Pipeline]
```

---

## 8. Testing

### 8.1 E2E Tests (existing location)

Update `Image-Prism/apps/metachromatic/e2e/seed-scout.spec.ts`:

```typescript
test('Step 1: Character selector loads archetypes and models', async ({ page }) => {
  // Mock /characters endpoint
  // Verify archetype groups render
  // Verify model radio buttons work
  // Verify "Next" button enables on selection
});

test('Step 2: Recommendations load from archetype preset', async ({ page }) => {
  // Mock /recommend endpoint with archetype data
  // Verify checkpoint, act, seed_range display
  // Verify profile notes visible
  // Verify buttons (Change Character, Customize, Run)
});

test('Step 3: Customize drawer allows edits', async ({ page }) => {
  // All fields editable
  // "Save as Preset" checkbox toggles
  // [Back] returns to Step 2
  // [Run Scout] goes to Step 4
});

test('Step 4: Scout running shows progress', async ({ page }) => {
  // Progress bar updates via SSE
  // Buttons work (Cancel, View Library)
});

test('Preset persistence: saved preset loads on next character select', async ({ page }) => {
  // Save preset in Step 3
  // Return to character selector
  // Re-select same character
  // Verify saved preset loads
});
```

### 8.2 Unit Tests

- `useSeedScoutStore`: state transitions, actions
- Recommendation loading logic: presets merge correctly
- Preset persistence: JSON writes/reads

---

## 9. Files Created / Modified

| File | Type | Description |
|---|---|---|
| `src/features/SeedScoutMode/SeedScoutMode.tsx` | New | Main container, step state machine |
| `src/features/SeedScoutMode/SeedScoutCharacterSelector.tsx` | New | Step 1 component |
| `src/features/SeedScoutMode/SeedScoutRecommendations.tsx` | New | Step 2 component |
| `src/features/SeedScoutMode/SeedScoutCustomize.tsx` | New | Step 3 component |
| `src/features/SeedScoutMode/SeedScoutRunning.tsx` | New | Step 4 component |
| `src/store/useSeedScoutStore.ts` | New | Zustand store |
| `src/features/SeedScoutMode/seed-scout.css` | New | Styling |
| `scripts/lora_pipeline/seed_api.py` | Modify | Add `/recommend` endpoint |
| `.agents/character_profiles/{ethnicity}_archetype.json` | Modify | Add `scout_preset` block to all 30+ archetypes |
| `.agents/character_profiles/full/{name}_full.json` | Modify | Add optional `scout_preset` block (user-writable) |
| `src/routes.tsx` | Modify | Add `/ai-training/seed-scout` route |
| `src/features/UnifiedAITrainingHub.tsx` | Modify | Add "Seed Scout" tab |
| `Image-Prism/apps/metachromatic/e2e/seed-scout.spec.ts` | Modify | Update tests for new flow |

---

## 10. Out of Scope

- Multi-character comparison in scout
- Seed sharing / export
- Advanced filtering (by tier, ethnicity, etc.) in character selector
- Alternative UI layouts (this design is final)
- Mobile/web-only support (Electron desktop only)

---

## 11. Success Metrics

✅ User selects character in <2 clicks
✅ Recommendations load in <500ms
✅ Presets persist across sessions
✅ Zero TypeScript errors
✅ All E2E tests passing
✅ No regressions in existing Seed Library functionality
