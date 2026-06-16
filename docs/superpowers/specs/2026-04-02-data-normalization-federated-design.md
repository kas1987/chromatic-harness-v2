# Data Normalization Design: Federated Schemas + Registry

**Date:** 2026-04-02  
**Scope:** Models DB, Character Profiles, Narrative Arcs  
**Timeline:** Blocking repair (weeks) + sustainable architecture  
**Strategy:** Federated schemas + explicit sync + validation guards

---

## Context

Current state: three interconnected systems with sync drift and metadata inconsistency.
- **Models DB:** 98% core-complete after repair, but normalization is root cause of sync breaks
- **Character Profiles:** 30+ ethnicity JSONs with naming inconsistency (`_full` vs `_archetype` variants)
- **Narrative Arcs:** beat structures + photography_direction + ethnicity overlays (separate files)

Problem statement: **Bad normalization → data sync breaks → validation can't catch it**

Solution: Each domain owns its schema, validation is local, sync points are explicit and auditable.

---

## Section 1: Canonical Schemas

Each domain has a formal schema (JSON Schema enforced at write-time):

### Models DB Schema
**Core fields:**
- `model_name`, `model_slug` (unique identifier)
- `nationality` (country-name format: "Ukraine", "Russia", "Spain")
- `ethnicity` (enum: 12 canonical values)
- `profession_primary`, `profession_tags` (derived from profession field)
- `aurora_tier` (1-8 or NULL; rendering confidence predictor)
- `face_taxonomy_id` (link to face taxonomy; nullable, 43% coverage)

**Constraints:**
- `ethnicity` ∈ {ukrainian, russian, lebanese, persian, spanish, french, colombian, ethiopian, nigerian, indian, japanese, korean} (12 canonical; see registry)
- `nationality` must be valid country name (not slang or alternate spellings)
- `aurora_tier` ∈ {1, 2, 3, 4, 5, 6, 7, 8, NULL}
- `model_name` and `model_slug` must not be NULL

**Validation:** on write, before commit to DB. Reject non-canonical values (e.g., "ukranian" typo, "europe" as ethnicity).

### Character Profile Schema
**Core fields:**
- `ethnicity` (reference to Models.ethnicity; validates against canonical list)
- `nationality` (reference to Models.nationality; must resolve to valid country)
- `personality_axes` (object with emotion/sexuality/dominance/intelligence axes; each axis ∈ {1-10} scale, defined in registry)
- `voice_profile` (TTS voice ID + settings)
- `arc_affinity` (list of arc_name strings where this character is recommended; must resolve to valid arcs)

**Constraints:**
- `ethnicity` must exist in Models as valid canonical value
- `nationality` must match Models for any linked character entry
- `personality_axes` vocab is defined (see registry below)
- `arc_affinity` references must exist in narrative arcs

**Validation:** on load, all foreign-key references must resolve. If broken, raise `SYNC_BROKEN` state (don't auto-repair).

### Narrative Arc Schema
**Core fields:**
- `arc_name` (unique identifier)
- `beats[]` (ordered list of narrative beats)
  - `beat.name`, `beat.description`
  - `beat.photography_direction` (lens/lighting/aesthetic/prompt_tokens)
- `ethnicity_overlays[]` (customizations per ethnicity)
  - `ethnicity` (reference to canonical ethnicity)
  - `lighting_override`, `warmth_injection`, `expression_progression`

**Constraints:**
- `ethnicity_overlays[].ethnicity` must exist in Models.ethnicity (canonical list)
- `beat.photography_direction` has consistent structure across all beats
- Beat order is immutable (changes require arc version bump)

**Validation:** on load, all ethnicity_overlays must resolve to valid ethnicity values. Flag arc as "ethnicity mismatch" if not.

---

## Section 2: Sync Points & Data Contracts

Sync happens at **explicit boundaries** with validation guards:

### Models DB → Character Profile
**Trigger:** when Models.ethnicity or Models.nationality changes  
**Sync rule:** find all Character profiles with this ethnicity; validate that nationality still resolves  
**Validation gate:** Character.ethnicity must exist in Models as valid canonical value  
**Failure mode:** sync blocks until manual review (don't auto-repair)  
**Example:** Models.ethnicity changes "ukraine" → "ukrainian"; all Ukrainian characters re-validated

### Models DB → Narrative Arc
**Trigger:** when Models.ethnicity changes  
**Sync rule:** update arc_affinity field (which arcs recommend this character/ethnicity)  
**Validation gate:** all ethnicity_overlays in Arc must exist in Models.ethnicity  
**Failure mode:** flag arc as "ethnicity mismatch" until fixed  
**Example:** New ethnicity added to Models; arcs are scanned, unmatched overlays flagged

### Character Profile ↔ Arc (bidirectional)
**Trigger:** when Arc assigns a character, or Character declares arc affinity  
**Sync rule:** both directions must agree (Character says "russian_arc", Arc says Character belongs)  
**Validation gate:** cross-check on load; both must reference valid Models entries  
**Failure mode:** prefer Character as source-of-truth, flag Arc as stale  
**Resolution:** Character.arc_affinity is authoritative; Arc.characters is derived view

---

## Section 3: Validation Layer & External Tooling

### Validation Architecture

**Pre-write validation (Models DB)**
- Schema validator runs before each insert/update
- Rejects non-canonical values (ethnicity typo, invalid aurora_tier, null model_name)
- Blocks commit until fixed

**Post-load validation (Character & Arc)**
- On load, validate all foreign-key references resolve
- If broken, raise `SYNC_BROKEN` state (visible to user, don't auto-repair)
- User reviews and chooses repair action

**Registry**
- Single source of truth for all schema definitions + valid value lists
- Includes: ethnicity enum, nationality enum, personality vocab, aurora tier definitions
- Lives in code, versioned with git
- Example: `.agents/schema-registry/ethnicity.json`, `.agents/schema-registry/personality-vocab.json`

### Repair Strategy

**Discovery phase**
- Scan all three systems, flag violations
- Output: violation report (invalid ethnicity, broken links, mismatched sync, orphaned data)
- User reviews and decides next step

**Repair phase**
- User applies fix (delete orphan, fix typo, re-link)
- Validation confirms fix before commit
- Audit log records action + rationale

**Prevention phase**
- Git hook blocks commits with invalid data
- Nightly audit reports drift (if sync has diverged since last check)
- Pre-generation validation ensures downstream systems only see clean data

### External Repo Integration

**Schema validation & enforcement:**
- Data validation tool (e.g., Dify workflow-driven validation, or lightweight JSON Schema validator)
- Validates all writes, rejects non-canonical values at source

**Data sync & contracts:**
- Data contract library (e.g., Flowise contract-based data flows, or custom sync validator)
- Detects drift between Models DB ↔ Character ↔ Arc
- Validates sync rules are enforced

**Quality gates:**
- Git hook infrastructure to block bad data commits
- Pre-generation validation (before ComfyUI job submission)
- Nightly audit reports (spot-check system health)

---

## Implementation Order

1. **Registry** (days 1-2): define all schemas + valid value lists, commit to git
2. **Pre-write validation** (days 3-4): Models DB validator, gate all writes
3. **Post-load validation** (days 5-6): Character + Arc loaders, raise SYNC_BROKEN on failure
4. **Discovery** (days 7-8): scan all three systems, generate violation report
5. **Repair** (days 9-15): user-guided repairs, validation confirms each fix
6. **Prevention** (days 16+): git hooks, nightly audits, pre-generation validation

---

## Success Criteria

- [ ] All Models DB fields are canonical (no invalid ethnicity, nationality, aurora_tier values)
- [ ] All Character profiles resolve to valid Models entries (no broken ethnicity/nationality links)
- [ ] All Narrative arcs reference valid ethnicity overlays (no missing ethnicity definitions)
- [ ] Sync drift is detected within 24h of occurrence (nightly audit)
- [ ] Zero generation failures due to metadata inconsistency (validated pre-submission)
- [ ] New data sources can be onboarded with confidence (schema validation prevents bad data from entering)

