# NSFW Cumshot/Bukkake Dataset Organization Design
**Date:** 2026-03-25
**Dataset:** 184 cumshot/bukkake images + reference metadata
**Goal:** Organize by prompt-aligned dimensions for reproducible model testing

---

## 1. Folder Structure

Organized by **primary prompt dimensions** extracted from metadata analysis:

```
E:\.02_Zceleb_images\NSFW_Master\nsfw_consolidated_master\
├── _organized/                                    # Main organized dataset
│   ├── by-placement/
│   │   ├── facial/                               # 180 images (97.8%)
│   │   │   ├── image_00001.jpg
│   │   │   ├── image_00001.txt (original metadata)
│   │   │   └── ...
│   │   ├── on-body/                              # Variable coverage
│   │   └── in-mouth/                             # Swallowing/oral focus
│   ├── by-coverage/
│   │   ├── complete/                             # 161 images (87.5%)
│   │   ├── partial/
│   │   └── drenched/                             # 7 images (3.8%)
│   ├── by-volume/
│   │   ├── 1-5-loads/
│   │   ├── 6-10-loads/                           # 109 images (59.2%)
│   │   └── 10plus-loads/
│   ├── by-pattern/
│   │   ├── spray/                                # 1 image
│   │   ├── splatter/                             # 11 images
│   │   ├── dripping/                             # 55 images (29.9%)
│   │   └── layered/
│   ├── by-texture/
│   │   ├── thick/                                # 53 images (28.8%)
│   │   ├── creamy/
│   │   └── runny/                                # 1 image
│   └── test-sets/                                # Pre-assembled test batches
│       ├── baseline-facial-heavy.csv             # Facial + 10+ loads
│       ├── partial-coverage-test.csv             # Partial coverage variants
│       └── ...
├── _metadata/                                    # Original metadata archive
│   └── (original .txt files preserved)
├── catalog.csv                                   # Master index (single source of truth)
├── conversion-table.json                         # Folder → Prompt mapping
├── README.md                                     # Organization guide
└── scripts/
    ├── query-dataset.py                          # Query catalog by criteria
    ├── batch-test-set.py                         # Generate test sets
    └── generate-prompt.py                        # Image → Prompt conversion
```

---

## 2. Naming Convention

**File naming:** `image_{original_sequence}.jpg`

Example:
- Original: `00001_37695333_012_ac28.jpg`
- Organized: `image_00001.jpg` (semantic sequence number preserved)

**Folder slugs:** lowercase, hyphen-separated, prompt-aligned

Examples:
- `by-placement/facial/` → prompt keyword: "facial cumshot"
- `by-coverage/complete/` → prompt keyword: "complete coverage, drenched"
- `by-volume/10plus-loads/` → prompt keyword: "10+ loads, multiple men"

---

## 3. Master Catalog (CSV)

**File:** `catalog.csv`
**Purpose:** Single source of truth, queryable, reproducible

| image_id | filename | placement | coverage | volume | pattern | texture | original_tags | test_set | prompt_snippet |
|----------|----------|-----------|----------|--------|---------|---------|---------------|----------|-----------------|
| 1 | image_00001.jpg | facial | complete | 6-10 | dripping | thick | cumshot,blowjob,... | baseline | "facial cumshot, complete coverage" |
| 2 | image_00002.jpg | facial | complete | 6-10 | layered | thick | cumshot,bukkake,... | baseline | "facial cumshot, 10+ loads" |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

**Columns:**
- `image_id` — Sequence number (1-184)
- `filename` — Actual filename in organized folders
- `placement` — facial, on-body, in-mouth
- `coverage` — complete, partial, drenched
- `volume` — 1-5, 6-10, 10plus
- `pattern` — spray, splatter, dripping, layered
- `texture` — thick, creamy, runny
- `original_tags` — All 523 unique tags from original metadata
- `test_set` — Assigned test batch (if part of pre-assembled set)
- `prompt_snippet` — Auto-generated prompt components

---

## 4. Conversion Table (JSON)

**File:** `conversion-table.json`
**Purpose:** Folder path → Prompt keywords mapping

```json
{
  "placement": {
    "facial": {
      "prompt_component": "facial cumshot",
      "image_count": 180,
      "percentage": 97.8
    },
    "on-body": {
      "prompt_component": "cum on body",
      "image_count": 12,
      "percentage": 6.5
    }
  },
  "coverage": {
    "complete": {
      "prompt_component": "complete coverage, drenched",
      "image_count": 161,
      "percentage": 87.5
    },
    "partial": {
      "prompt_component": "partial coverage",
      "image_count": 16,
      "percentage": 8.7
    },
    "drenched": {
      "prompt_component": "excessive coverage, cum drenched",
      "image_count": 7,
      "percentage": 3.8
    }
  },
  "volume": {
    "1-5": {
      "prompt_component": "single cumshot, light load",
      "image_count": 24,
      "percentage": 13.0
    },
    "6-10": {
      "prompt_component": "6-10 loads, multiple cumshots",
      "image_count": 109,
      "percentage": 59.2
    },
    "10plus": {
      "prompt_component": "10+ loads, bukkake, gangbang",
      "image_count": 51,
      "percentage": 27.7
    }
  },
  "pattern": {
    "spray": {
      "prompt_component": "spray cumshot, spraying",
      "image_count": 1,
      "percentage": 0.5
    },
    "splatter": {
      "prompt_component": "splatter cumshot, splattering",
      "image_count": 11,
      "percentage": 6.0
    },
    "dripping": {
      "prompt_component": "dripping cum, cum dripping",
      "image_count": 55,
      "percentage": 29.9
    },
    "layered": {
      "prompt_component": "layered cumshot, multiple layers",
      "image_count": 68,
      "percentage": 37.0
    }
  },
  "texture": {
    "thick": {
      "prompt_component": "thick cum, thick cumshot",
      "image_count": 53,
      "percentage": 28.8
    },
    "creamy": {
      "prompt_component": "creamy cum, creamy texture",
      "image_count": 28,
      "percentage": 15.2
    },
    "runny": {
      "prompt_component": "runny cum, liquid",
      "image_count": 1,
      "percentage": 0.5
    }
  }
}
```

---

## 5. Workflow

### 5a. Image Organization
1. Read all 184 images + metadata from root
2. Parse existing .txt tags
3. Categorize each image by (placement, coverage, volume, pattern, texture)
4. **Symlink images** to appropriate folders (non-destructive)
5. **Copy original .txt** metadata alongside each symlink
6. Preserve originals in `_metadata/` archive

### 5b. Catalog Generation
1. For each image, extract primary dimensions
2. Generate `prompt_snippet` from conversion table
3. Write one row per image to `catalog.csv`
4. Catalog becomes query interface + reproducibility record

### 5c. Test Set Assembly
Example pre-assembled sets:
- `baseline-facial-heavy.csv` — All facial + 10+ loads (n=47)
- `partial-coverage-test.csv` — Partial coverage only (n=16)
- `pattern-variants.csv` — All patterns represented (n=69)

---

## 6. Tools & Scripts

### `query-dataset.py`
```bash
python query-dataset.py --placement facial --coverage complete --volume 10plus
# Returns: image list + prompt components
```

### `batch-test-set.py`
```bash
python batch-test-set.py --name baseline-facial-heavy --criteria "placement=facial AND volume=10plus"
# Generates CSV + sample prompts
```

### `generate-prompt.py`
```bash
python generate-prompt.py --image image_00001.jpg
# Output: "facial cumshot, 6-10 loads, complete coverage, dripping, thick cum"
```

---

## 7. Example Output

### Folder after organization:
```
E:\.02_Zceleb_images\NSFW_Master\nsfw_consolidated_master\
├── _organized/
│   ├── by-placement/facial/
│   │   ├── image_00001.jpg (symlink)
│   │   ├── image_00001.txt
│   │   ├── image_00002.jpg (symlink)
│   │   ├── image_00002.txt
│   │   └── ... (180 total)
│   ├── by-coverage/complete/
│   │   ├── image_00001.jpg (symlink)
│   │   ├── image_00001.txt
│   │   └── ... (161 total)
│   └── ...
├── catalog.csv (184 rows)
├── conversion-table.json
└── scripts/
```

### Sample catalog.csv rows:
```
1,image_00001.jpg,facial,complete,6-10,dripping,thick,"cumshot, blowjob, oral finish, facial from oral, ...","baseline-facial-heavy","facial cumshot, 6-10 loads, complete coverage, dripping, thick cum"
2,image_00002.jpg,facial,complete,6-10,layered,thick,"cumshot, blowjob, gangbang, ...","baseline-facial-heavy","facial cumshot, 10+ loads, bukkake, complete coverage, layered"
```

### Sample query result:
```bash
$ python query-dataset.py --placement facial --volume 10plus
image_00047.jpg  →  "facial cumshot, 10+ loads, bukkake, complete coverage, dripping"
image_00089.jpg  →  "facial cumshot, 10+ loads, bukkake, complete coverage, thick cum"
... (51 images match)
```

---

## 8. Benefits

| Use Case | How Solved |
|----------|-----------|
| **Reproducibility** | Catalog pins exact image sets used in tests |
| **Prompt correlation** | Conversion table auto-generates keywords from folder |
| **Visual browsing** | Folder structure mirrors how you think about cumshots |
| **Batch testing** | Query catalog for "all images with X+Y characteristics" |
| **Traceability** | `test_set` column records which images went into which tests |
| **Non-destructive** | Symlinks preserve originals, originals in `_metadata/` archive |
| **Scalable** | New images: add row to CSV + symlink to folders |

---

## 9. Implementation Steps

1. **Create folder structure** — `_organized/` with 5 dimension folders
2. **Generate catalog.csv** — Parse all metadata, categorize, build CSV
3. **Create conversion-table.json** — Map folders → prompt keywords
4. **Symlink images** — Non-destructive (originals stay in root + `_metadata/`)
5. **Write query scripts** — Python CLI tools for batch operations
6. **Test with proof-of-concept** — Organize first 10 images, verify workflow
7. **Full organization** — Run on all 184 images
8. **Generate test sets** — Pre-assemble common test combinations

---

## 10. Timeline & Scope

- **Phase 1 (Proof-of-Concept):** 10 sample images, catalog, scripts (1-2 hours)
- **Phase 2 (Full Organization):** All 184 images, test sets (30 min automated)
- **Phase 3 (Validation & Docs):** Run queries, document usage, test scripts (1 hour)

**Total effort:** ~4 hours, mostly automated

---

## 11. Non-Destructive Approach

- Original images stay in root directory
- Original `.txt` metadata archived in `_metadata/`
- Symlinks created to organized folders (safe, reversible)
- Catalog is CSV (human-readable, version-controllable)
- No file moves = no risk of data loss
