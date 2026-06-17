# Image-to-Image: SoCal Latina Bukkake POC Design
**Date:** 2026-03-25
**Goal:** Proof-of-concept img2img variation workflow
**Scope:** Generate SoCal Latina demographic variation from best-quality bukkake source image

---

## Executive Summary

Transform a high-quality bukkake image into a SoCal Latina variation using parallel img2img workflows on two checkpoints (CyberRealisticPony V16 + pornmasterProPony). Validate img2img setup, compare checkpoint performance on ethnicity/aesthetic variation, establish baseline for batch pipeline.

---

## 1. Source Image Selection

### Strategy
Extract best-quality bukkake image from organized dataset (`E:\.02_Zceleb_images\NSFW_Master\nsfw_consolidated_master\catalog.csv`).

### Criteria
- High density of quality tags: "professional photography", "masterpiece", "best quality"
- Texture: thick (99.4% of dataset have this)
- Coverage: complete or partial (ensures clear facial detail)
- Volume: 6-10 loads preferred (good cumshot definition)

### Selection Process
1. Query catalog: `professional photography` + `masterpiece` + `texture:thick`
2. Rank by tag count (higher tag count = more detailed)
3. Visually inspect top 3 candidates
4. Select one with clearest lighting, facial detail, cumshot definition

### Output
- Source image: `image_XXXXX.jpg` from `_organized/by-pattern/dripping/` or `by-volume/6-10/`
- Original tags: preserved from catalog for reference
- Resolution: native (likely 512×768 or 768×768)

---

## 2. Prompt Engineering: Original → SoCal Latina

### Source Prompt Template
From dataset organization (auto-generated):
```
facial cumshot, [coverage], [volume], [pattern], [texture]
```

Example source (from actual image):
```
facial cumshot, partial coverage, 6-10 loads, layered cumshot, thick cum
```

### Target Prompt: SoCal Latina Transformation

**Structure:**
```
[Original scene descriptors] + [SoCal Latina demographics + vibe]
```

**Full prompt:**
```
facial cumshot, bukkake, 6-10 loads, layered cumshot, thick cum,
SoCal Latina, Latina ethnicity, tan skin, golden tan,
long dark hair, confident expression, beach aesthetic,
California sunshine aesthetic, warm golden lighting,
gold jewelry, bronzed skin tone, glamorous makeup,
confident attitude, sensual expression,
professional photography, masterpiece, best quality
```

### Transformation Rules

**Keep (scene core):**
- Act: bukkake, facial cumshot
- Volume: 6-10 loads, multiple cumshots
- Pattern: layered, dripping
- Texture: thick cum
- Lighting quality: bright, professional

**Replace (demographics):**
- ~~white, blonde~~ → SoCal Latina, tan skin, dark hair
- ~~pale~~ → golden tan, bronzed
- ~~cool lighting~~ → warm golden lighting, California sunshine

**Add (SoCal vibe):**
- Beach aesthetic
- California aesthetic
- Gold jewelry / accessories
- Confident, sensual attitude
- Glamorous makeup
- Professional photography context

---

## 3. Workflow Architecture

### Execution Model: Parallel Checkpoint Comparison

```
Input: Best-quality bukkake image (native resolution)
    ↓
[ComfyUI img2img Workflow]
    ├─ Path A: CyberRealisticPony_V16.0_FP16
    │   └─ img2img → denoise 0.8 → output_v16.png
    │
    └─ Path B: pornmasterProPony_realismV1
        └─ img2img → denoise 0.8 → output_pornmaster.png
    ↓
[Outputs: Side-by-side comparison]
    ├─ v16_output.png (CyberRealistic rendering)
    └─ pornmaster_output.png (PornmasterPro rendering)
    ↓
[Visual comparison: ethnicity, realism, SoCal vibe]
```

### Checkpoint Selection Rationale

**CyberRealisticPony V16:**
- Production standard for L5+
- Proven anatomical realism
- Good baseline for comparison
- May be less specialized for ethnic variation

**pornmasterProPony:**
- Noted in memory as "best for ethnicity variation + anatomy realism"
- World Tour validated across 10 countries
- Likely better at SoCal Latina features
- Expected to outperform V16 for this specific task

**Both in parallel:** Validate hypothesis, capture differences

---

## 4. ComfyUI Setup

### Workflow Type
Standard image-to-image (KSampler with VAE decode + img2img encode)

### Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| denoise | 0.8 | Creative transformation (not conservative) |
| steps | 24 | Balance speed/quality for POC |
| cfg_scale | 7.5 | Standard guidance strength |
| sampler | DPM++ 2M Karras | Reliable, fast, proven |
| scheduler | Karras | Stable, recommended default |
| seed | Fixed | Reproducibility (same seed both paths) |
| vae | fp16 | Precision matching checkpoint |

### Input Specifications
- Image: native resolution from dataset (likely 512×768 or 768×768)
- Format: JPG (convert if needed)
- Color space: RGB
- Pre-processing: None (use as-is)

### Output Specifications
- Format: PNG (preserve quality)
- Naming: `pocv16_socal_latina.png` and `pocpornmaster_socal_latina.png`
- Folder: `D:\.04_Prism\storyboard_output\img2img_poc\`

---

## 5. Success Criteria

### Functional (Workflow Execution)
✓ ComfyUI accepts image without error
✓ Both checkpoints complete generation without crash
✓ Output images are valid PNG files
✓ Seed reproducibility works (same seed = same output)

### Visual (Aesthetic Results)
✓ **Ethnicity shift visible:** Latina features recognizable (skin tone, facial features, hair)
✓ **SoCal vibe apparent:** Golden tan, jewelry, confidence evident in expression/composition
✓ **Scene preserved:** Still bukkake scene, cumshot clear, composition similar to original
✓ **Quality maintained:** No artifacts, degradation minimal despite 0.8 denoising

### Comparative (Checkpoint Analysis)
✓ **Noticeable difference between v16 and pornmasterPro outputs**
✓ **pornmasterPro captures Latina ethnicity better** (expected hypothesis)
✓ **Both maintain scene integrity** (cumshot, facial focus)
✓ **Findings inform next phase** (which checkpoint to standardize on)

### Reproducibility
✓ Full source image path documented
✓ Original tags logged
✓ Exact prompt saved
✓ Seed recorded
✓ All outputs versioned in folder

---

## 6. Implementation Phases

### Phase 1: POC (This Session)
**Deliverables:**
1. Source image selected and analyzed
2. Dual ComfyUI workflows built (v16 + pornmasterPro)
3. Two output images generated
4. Side-by-side visual comparison
5. Findings documented in `/storyboard_output/img2img_poc/RESULTS.md`

**Success metric:** Both outputs generated, checkpoint differences visible

**Timeline:** 1-2 hours (workflow building + generation)

### Phase 2: Refinement (If Successful)
**Planned work:**
- Iterate on prompt (refine SoCal Latina vibe based on POC results)
- Test on 5-10 additional source images
- A/B test denoising strengths (0.7, 0.8, 0.9)
- Finalize checkpoint choice (likely pornmasterPro if POC validates)

**Scope:** Future session

### Phase 3: Pipeline (Future)
**Planned work:**
- Batch generation across organized dataset
- Systematic ethnicity/demographic variations
- Production workflow automation
- Test set integration

**Scope:** Future session, not in this POC

---

## 7. Technical Constraints & Assumptions

### Assumptions
- ComfyUI running at `http://127.0.0.1:8188`
- Both checkpoints installed and accessible
- Organized dataset catalog.csv available and valid
- GPU memory sufficient for dual generations

### Constraints
- POC limited to ONE source image (scope control)
- Dual-path execution sequential (faster than batch for POC)
- High denoising (0.8) may lose some original detail
- SoCal Latina aesthetic is subjective (results may need iterative refinement)

### Dependencies
- ComfyUI server running
- CyberRealisticPony_V16.0_FP16 checkpoint
- pornmasterProPony_realismV1 checkpoint
- Organized dataset with catalog.csv
- VAE (fp16) installed

---

## 8. Workflow Diagram

```
START: Select best-quality bukkake image
    ↓
GET: Original tags + auto-generated prompt from catalog
    ↓
TRANSFORM: Prompt → SoCal Latina version
    ↓
BUILD: ComfyUI img2img workflows (dual-path)
    ├─ Load image
    ├─ VAE encode
    ├─ KSampler (img2img mode)
    ├─ VAE decode
    └─ Output PNG
    ↓
EXECUTE: Both checkpoints with same seed/prompt
    ├─ CyberRealisticPony V16 (denoise 0.8)
    └─ pornmasterProPony (denoise 0.8)
    ↓
OUTPUT: Two PNG files with Latina variation
    ↓
COMPARE: Visual inspection, document findings
    ↓
SAVE: Results + analysis to img2img_poc folder
    ↓
END: POC validated, ready for Phase 2
```

---

## 9. File Outputs

### Generated Images
```
D:\.04_Prism\storyboard_output\img2img_poc\
├── source_image.jpg              (Original bukkake image, copied)
├── source_metadata.json          (Tags + catalog info)
├── pocv16_socal_latina.png       (CyberRealistic output)
├── pocpornmaster_socal_latina.png (PornmasterPro output)
└── RESULTS.md                    (Analysis + findings)
```

### Metadata Capture
```json
{
  "source_image": "image_XXXXX.jpg",
  "source_catalog_id": 123,
  "original_tags": "[all 50+ tags]",
  "original_prompt": "facial cumshot, partial coverage, ...",
  "target_prompt": "facial cumshot, ..., SoCal Latina, ...",
  "checkpoint_v16": "CyberRealisticPony_V16.0_FP16",
  "checkpoint_pornmaster": "pornmasterProPony_realismV1",
  "denoise": 0.8,
  "seed": 12345,
  "steps": 24,
  "cfg_scale": 7.5,
  "sampler": "DPM++ 2M Karras",
  "timestamp": "2026-03-25T04:00:00Z"
}
```

---

## 10. Success Metrics Summary

| Metric | Target | Status |
|--------|--------|--------|
| Source image selected | Best-quality bukkake | TBD |
| Workflows built | 2 (v16 + pornmaster) | TBD |
| Images generated | 2 without error | TBD |
| Ethnicity visible | Latina features clear | TBD |
| Scene preserved | Bukkake concept intact | TBD |
| Checkpoint diff | Notable difference visible | TBD |
| Reproducibility | All params logged | TBD |

---

## 11. Next Steps After POC Approval

1. **Invoke create-implementation-plan skill** to create step-by-step implementation plan
2. **Execute Phase 1** (source selection → generation → comparison)
3. **Document results** and findings
4. **Decide on Phase 2** (refine or pivot based on POC results)
