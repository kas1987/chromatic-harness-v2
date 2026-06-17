# Model Discovery & Enrichment Pipeline — Design Spec

**Date:** 2026-03-30
**Owner:** User
**Status:** Design Approved
**Context:** Expand model roster from 100 verified performers to 150+ with full metadata enrichment + discovery of trending newer models (2-3 years in)

---

## Executive Summary

Build a **3-phase parallel agent pipeline** that:
1. **Scrapes & validates** 100+ IAFD performers with complete act/career data
2. **Enriches metadata** with character matching, arc beat fit, and social proof
3. **Discovers trending** newer models (last 2-3 years) across 5+ platforms
4. **Consolidates** into canonical JSON + updated database as source of truth for character casting

**Deliverable:** Updated `D:\.000_AI\models.db` + canonical JSON export + HTML discovery report

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  LAUNCH 3 PARALLEL AGENT GROUPS (Day 1)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Group 1: IAFD Scraper          Group 2: Enrichment            │
│  (10-15 agents)                 (5-10 agents)                  │
│  ├─ Top 100 performers          ├─ Consume Group 1 output      │
│  ├─ Act breakdown               ├─ Character matching          │
│  ├─ Career dates                ├─ Arc beat fit                │
│  └─ Image URLs                  └─ Signature traits            │
│                                                                 │
│  Group 3: Discovery Scouts       Consolidation                 │
│  (8-12 agents)                   (1 agent, runs last)          │
│  ├─ Twitter/X trending          ├─ Merge all data              │
│  ├─ Reddit communities          ├─ Deduplicate                 │
│  ├─ Patreon/OnlyFans            ├─ Update models.db            │
│  ├─ IAFD new additions          ├─ Export JSON                 │
│  ├─ Studio releases             └─ Generate report             │
│  └─ Traction scoring                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Timeline: Groups 1-3 run in parallel (Days 1-3)
          Consolidation (Day 3-4)
          Report generation (Day 4)
```

### Agent Group Specifications

#### **Group 1: IAFD Data Scraper (10-15 agents)**

**Purpose:** Collect baseline act/career data for 100+ performers

**Input:**
- `EXPANDED_ROSTER_TOP_50.json` (already created)
- Additional IAFD performer queries (trending, high-volume, specialty categories)

**Process per agent:**
1. Query IAFD for model profile
2. Extract: career dates, total scene count, all acts with counts
3. Download profile image + scene preview images (10-20 per model)
4. Validate data completeness (fail if <5 fields missing)
5. Write to `models_staging_iafd.json` (append-safe, JSON-L format)

**Output:** `D:\.04_Prism\models_staging_iafd.json` (JSON-L, 1 object per line)
- Format: `{"model_id": X, "name": "...", "acts": {...}, "images": [...], "career_dates": {...}}`

**Parallelization:** 10-15 agents, each scraping 7-10 models (non-overlapping ranges)

**Error handling:**
- 404/timeout → Skip, log to `scraper_failures.log`
- Partial data → Accept if >70% fields complete, mark as "incomplete"
- Rate limits → Exponential backoff, respect 1-2 sec delays between requests

---

#### **Group 2: Metadata Enrichment (5-10 agents)**

**Purpose:** Transform raw IAFD data into context-rich, character-matched profiles

**Input:** Real-time consumption of `models_staging_iafd.json`

**Process per agent:**
1. Read staged model data
2. **Character Archetype Matching:**
   - Compare specialization profile (anal %, lesbian %, etc.) to fictional characters
   - Score fit (0-100) for Ukrainian, Russian, Lebanese, Colombian, etc.
   - Return top 3 matches with reasoning

3. **Arc Beat Recommendation:**
   - Analyze top acts
   - Recommend beats (foreplay_intimate, penetrative_climax, group_oral, etc.)
   - Flag unsuitable beats (e.g., romantic_foreplay for anal specialists)

4. **Signature Traits:**
   - Derive from specialization + career arc
   - Dominance level (analyze % of top/bottom acts)
   - Personality vibe (e.g., "commanding, intense, no-nonsense")
   - Notable achievements (filter from career timeline + act diversity)

5. **Content Warnings:**
   - Flag if >30% extreme acts (DAP, fisting, watersports)
   - Note any rare specializations

6. Write to `models_enriched.json` (streaming, append-safe)

**Output:** `D:\.04_Prism\models_enriched.json` (context_rich schema, see below)

**Parallelization:** 5-10 agents, consuming from staging queue

**Idempotency:** Safe to re-run; agents check if model already enriched before processing

---

#### **Group 3: Discovery Scouts (8-12 agents)**

**Purpose:** Find trending newer models (2-3 years active) with traction

**Platforms & Approach:**

| Platform | Scraper Type | Traction Metrics | Image Sources |
|----------|---|---|---|
| **Twitter/X** | API or Selenium | Followers, RT/engagement ratio, hashtag trending | Profile + linked images |
| **Reddit** | Web scraper | Subreddit mentions, upvotes, post frequency | Imgur links in threads |
| **Patreon** | Selenium (login required) | Creator tier data, subscriber count trends | Creator posts |
| **OnlyFans** | Proxy/API (if available) | Subscriber count, post frequency | OnlyFans profile |
| **IAFD** | Query recent additions | Scene count, debut date (last 24 months) | IAFD profile |
| **Adult studios** | Scrape release calendars | New talent releases, featured videos | Studio preview images |

**Process per agent:**
1. Assign to 1-2 platforms
2. Scrape with platform-specific approach (respect ToS + rate limits)
3. Filter candidates:
   - Debut year >= 2023 (2-3 years active)
   - Has images available
   - Appears on 2+ platforms OR scored >40 on hybrid traction
4. **Traction Scoring:**
   ```
   score = (followers_normalized * 0.4) +
           (scene_volume_normalized * 0.3) +
           (trending_velocity_normalized * 0.3)

   - followers_normalized: [0-10K] Twitter, [0-50K] Instagram, [0-1K] OnlyFans
   - scene_volume_normalized: scenes in last 6 months
   - trending_velocity_normalized: growth rate (followers/week, mentions/week)
   ```
5. Collect 10-20 images per candidate (save with model slug)
6. Write to `models_discoveries.json` (with traction_score)

**Output:** `D:\.04_Prism\models_discoveries.json` (ranked by traction_score descending)
- Format: `{"name": "...", "debut_year": 2023, "platforms": [...], "traction_score": 65.4, "images": [...], "discovery_sources": [...]}`

**Parallelization:** 8-12 agents, each focused on 1-2 platforms

**Error handling:**
- Platform unavailable → Log, move to next
- Rate limit → Backoff, retry next batch
- Image download fails → Skip image, continue with metadata
- No images found → Flag as "image_incomplete", include anyway

---

#### **Consolidation Phase (1 agent, runs after Groups 1-3 complete)**

**Purpose:** Merge staged data into canonical database + JSON export

**Process:**
1. Wait for Groups 1-3 to complete (poll for completion)
2. Read `models_staging_iafd.json` + `models_enriched.json` + `models_discoveries.json`
3. **Deduplication:**
   - Match by name, slug, or image hash (if name conflicts)
   - Merge existing models (keep enriched data if present)
   - Flag duplicates in `consolidation_report.log`
4. **Database Update:**
   - INSERT or UPDATE `models` table with enriched columns
   - INSERT into `model_acts` if acts data missing
   - INSERT new models from discoveries
   - Create indices on specialization, traction_score, character_archetype
5. **JSON Export:**
   - Generate canonical JSON from database
   - Organize by: specialization_tier, traction_score, character_fit
   - Output to `D:\.04_Prism\models_canonical_export.json`
6. **Report Generation:**
   - HTML summary: 100+ existing, 50-100+ new discoveries
   - Trending up-and-comers (top 20 by traction_score)
   - Character matching matrix
   - Recommendations for priority models

**Output:**
- Updated `D:\.000_AI\models.db`
- `D:\.04_Prism\models_canonical_export.json`
- `D:\.04_Prism\discovery_report.html`
- `D:\.04_Prism\consolidation_report.log`

---

## Data Schemas

### JSON Schema: Context-Rich Model Profile

```json
{
  "model_id": 12345,
  "name": "Veronica Leal",
  "slug": "veronica-leal",
  "status": "active|semi-retired|retired",

  "career": {
    "debut_year": 2013,
    "peak_years": [2015, 2016, 2017],
    "current_status": "semi-active",
    "total_scenes": 1028,
    "last_scene_date": "2022-06-15"
  },

  "specializations": {
    "primary": "anal",
    "primary_percentage": 41.5,
    "top_3": [
      {"act": "anal", "scenes": 427, "percentage": 41.5},
      {"act": "ass_to_mouth", "scenes": 261, "percentage": 25.4},
      {"act": "squirt", "scenes": 239, "percentage": 23.2}
    ]
  },

  "signature_traits": {
    "dominance_level": "high|medium|low",
    "personality_vibe": "commanding, no-nonsense, intense pleasure responses",
    "notable_achievements": [
      "IAFD Anal Queen 2017",
      "Featured in 15 mainstream studios"
    ],
    "signature_scenes": [
      "Intense double penetration sequences",
      "Athletic squirting performances"
    ]
  },

  "character_matching": {
    "best_fit_archetypes": [
      {
        "archetype": "Ukrainian",
        "fit_score": 92,
        "reasoning": "Directness + dominance align with assertive character profiles"
      },
      {
        "archetype": "Lebanese",
        "fit_score": 88,
        "reasoning": "Intense pleasure response, warm undertones"
      }
    ]
  },

  "arc_beat_recommendations": {
    "ideal_beats": [
      "penetrative_climax",
      "group_escalation",
      "oral_penetrative_foreplay"
    ],
    "avoid_beats": [
      "romantic_foreplay",
      "intimate_conversation"
    ],
    "reasoning": "High-intensity acts, less suited for slow-burn romance"
  },

  "social_proof": {
    "twitter_followers": 245000,
    "twitter_engagement_rate": 3.2,
    "patreon_subscribers": 1200,
    "trending_mentions_30d": 340,
    "traction_score": 87.3,
    "discovery_source": "iafd|twitter|reddit|patreon|onlyfans"
  },

  "images": {
    "profile_urls": ["url1", "url2"],
    "scene_stills": ["url3", "url4", "url5"],
    "image_count": 45
  },

  "content_warnings": [
    "extreme_acts",
    "high_intensity"
  ]
}
```

### Database Schema: New Columns for `models` Table

```sql
-- Career tracking
ALTER TABLE models ADD COLUMN career_debut_year INT;
ALTER TABLE models ADD COLUMN career_peak_years TEXT; -- JSON array
ALTER TABLE models ADD COLUMN model_status TEXT; -- 'active|semi-retired|retired'

-- Specialization metadata
ALTER TABLE models ADD COLUMN primary_specialization TEXT;
ALTER TABLE models ADD COLUMN specialization_percentage REAL;
ALTER TABLE models ADD COLUMN top_3_specializations TEXT; -- JSON

-- Character matching
ALTER TABLE models ADD COLUMN character_archetypes TEXT; -- JSON array with scores
ALTER TABLE models ADD COLUMN arc_beat_recommendations TEXT; -- JSON

-- Signature traits
ALTER TABLE models ADD COLUMN personality_vibe TEXT;
ALTER TABLE models ADD COLUMN dominance_level TEXT;
ALTER TABLE models ADD COLUMN notable_achievements TEXT; -- JSON array

-- Social proof & discovery
ALTER TABLE models ADD COLUMN traction_score REAL;
ALTER TABLE models ADD COLUMN twitter_followers INT;
ALTER TABLE models ADD COLUMN patreon_subscribers INT;
ALTER TABLE models ADD COLUMN discovery_source TEXT;
ALTER TABLE models ADD COLUMN discovery_date TEXT; -- ISO date
ALTER TABLE models ADD COLUMN image_urls TEXT; -- JSON array

-- Content warnings
ALTER TABLE models ADD COLUMN content_warnings TEXT; -- JSON array
```

---

## Success Criteria

### Completion Metrics

- [ ] **100+ existing models** scraped with full act breakdown + images
- [ ] **50-100+ newer models** discovered (traction_score > 40)
- [ ] **100% enriched** context-rich JSON for top 100
- [ ] **Database** updated with all new columns + data
- [ ] **Zero duplicates** in final output (deduplication verified)
- [ ] **Image coverage** >90% (at least 10 images per model)
- [ ] **Character matching** completed for all 100+
- [ ] **Report generated** with discovery recommendations

### Quality Checks

- [ ] Acts data validation (>70% field completeness per model)
- [ ] Character matching accuracy (sample review of 10 models)
- [ ] Traction scoring consistency (verify calculations across 20 models)
- [ ] Image URLs active (spot-check 20 URLs)
- [ ] JSON schema compliance (validate against schema)

---

## Error Handling & Recovery

### Agent Failures

- **Group 1 scraper fails on model X:** Log to `scraper_failures.log`, skip, continue. Consolidation agent will report gaps.
- **Group 2 enrichment hangs:** Timeout after 5 min per model, mark as incomplete, continue.
- **Group 3 platform unavailable:** Try backup platforms, log outage, move to next.

### Data Quality Issues

- **Incomplete acts data:** Accept if >70% fields populated, mark as "incomplete" in database
- **Image download failures:** Skip image, include model data anyway
- **Duplicate detection:** Consolidation agent flags, manual review required for merge
- **Traction score invalid:** Recalculate with fallback to 0, log

### Recovery Protocol

1. Agents write to append-safe formats (JSON-L, not JSON)
2. Consolidation agent can resume mid-way
3. Re-run consolidation if database update fails
4. Manual dedup review if >5 duplicates detected

---

## Timeline & Dependencies

| Phase | Duration | Dependencies | Owner |
|-------|----------|---|---|
| **Setup** (create agents, staging dirs) | 0.5 days | None | User |
| **Group 1 (IAFD scrape)** | 2-3 days | Setup complete | Agents |
| **Group 2 (enrichment)** | 1-2 days | Group 1 >50% complete | Agents |
| **Group 3 (discovery)** | 2-3 days | Group 1 started | Agents |
| **Consolidation** | 0.5 days | All groups complete | Agent |
| **Report + handoff** | 0.5 days | Consolidation complete | User |

**Total wall-clock time:** 3-4 days (with parallelization)

---

## Assumptions & Constraints

- **IAFD access:** Assumes Babepedia/patchright scraper works (Cloudflare bypass available)
- **Platform ToS:** Agents respect rate limits, avoid aggressive scraping
- **Image storage:** Images downloaded locally or linked (not hosted by us)
- **Database size:** ~12MB expected (1000 models × 12KB average)
- **API availability:** Twitter/Patreon APIs may require auth tokens (assume available)

---

## Future Enhancements (Post-MVP)

- Real-time social proof updates (weekly refresh of follower counts)
- Automated character matching scoring (ML model instead of heuristic)
- Video preview integration (not just still images)
- Contractual/availability tracking (which models available for custom work)
- Earnings estimation (based on public Patreon/OnlyFans data)

---

**Design Doc Status:** ✅ Complete
**Ready for Implementation Plan:** Yes
