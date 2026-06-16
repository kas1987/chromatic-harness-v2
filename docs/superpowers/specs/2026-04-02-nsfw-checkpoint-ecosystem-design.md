---
title: NSFW Checkpoint Ecosystem Evaluation — CyberRealistic Anchoring with Scenario Decision Tree
date: 2026-04-02
status: approved
version: 1.0
---

<!-- markdownlint-disable -->

# NSFW Checkpoint Ecosystem Evaluation — CyberRealistic Anchoring with Scenario Decision Tree

**Goal:** Evaluate the full NSFW generation ecosystem (checkpoints, LoRAs, sampling, face processing, integration) with CyberRealistic V16 as production baseline, then build a scenario-based decision tree mapping NSFW generation tasks to optimal tool stacks.

**Context:** CyberRealistic is the current production checkpoint. Research determines when/why to deviate (which checkpoints excel where), how LoRAs compensate for gaps, which sampling tweaks maximize NSFW realism, and how face processing integrates into the overall pipeline.

**Success Criteria:**
- CyberRealistic comprehensively evaluated (strengths, anatomical accuracy, explicit content quality, known limitations)
- Checkpoint landscape mapped (Pony, NSFW, XL, Illustrious, Z-Image, others) with NSFW-specific scoring
- LoRA ecosystem catalogued (face, body, concept, skill) and matched to checkpoint gaps
- Sampling methods optimized for NSFW realism (DPM++, Euler, CFG scales, denoise, scheduler tweaks)
- Face processing integrated within checkpoint context (detection, extraction, swapping, consistency validation)
- Scenario-based decision tree built: if scenario = X, use checkpoint Y + LoRA Z + sampling W + face processing V
- Ready for implementation or pilot evaluation

---

## Scope

### In Scope
- **Checkpoints:** CyberRealistic V16 (deep-dive), Pony, NSFW, XL, Illustrious, Z-Image, RealisticVision, others in active use
- **LoRAs:** Face quality/identity (ReActor, face LoRAs), body/anatomical (Uber, regional, pose), concept/act (anal, oral, cum, MMF, explicit), skill (lighting, composition)
- **Sampling methods:** DPM++ (variants), Euler, CFG scales (impact on NSFW), denoise ranges, scheduler tweaks, seed stability
- **Face processing:** Detection (InsightFace, MTCNN), extraction (alignment), swapping (ReActor, alternatives), consistency validation (optical flow, embedding distance)
- **Scenario taxonomy:** Acts (facial, anal, oral, blowjob, cumshot variants), photography (editorial, raw, glamour, dark), anatomy (breast detail, fluid, skin tone), ethnicity (Lebanese, Ukrainian, Russian, Persian, Spanish, French, Colombian, Ethiopian, Indian), tier (L1-L7 vs L8), integration (multi-step pipelines)
- **Decision tree:** Scenario → (checkpoint, LoRA stack, sampling, face processing) mapping

### Not in Scope
- Real-time inference optimization (speed vs quality trade-offs)
- Commercial/proprietary checkpoints
- Non-NSFW-specific model evaluation (general purpose models assessed only if they appear in NSFW pipelines)
- Hardware constraints (assume GPU available)
- Legal/ethical considerations (evaluation is technical, not normative)

---

## Research Methodology

**Phase 1: CyberRealistic Deep-Dive (2 hours)**
- Current status: strengths, known limitations, anatomical accuracy on NSFW content
- Comparison to prior versions (V15, V14) — what improved?
- Community feedback (GitHub issues, Reddit, forums) on NSFW use cases
- Established best practices (sampling settings, negative prompts, LoRA combinations)

**Phase 2: Checkpoint Landscape (2-3 hours)**
- 6-8 checkpoints scored against NSFW criteria (ethnicity handling, anatomical fidelity, explicit content quality, body diversity, skin tone range)
- When to use each checkpoint (CRP for ethnicity, Uber for body/fluid, Pony for fantasy, etc.)
- Hardware requirements and inference speed per checkpoint
- LoRA compatibility per checkpoint

**Phase 3: LoRA Ecosystem (2-3 hours)**
- Face LoRAs: ReActor, face quality, identity preservation
- Body LoRAs: regional (Lebanese, Ukrainian), anatomical (curvy, petite, athletic), fluid/explicit
- Concept LoRAs: acts (anal, oral, cumshot), sexual positions, photography styles
- Skill LoRAs: lighting, composition, eye detail, makeup
- LoRA stacking best practices: weight ceilings, compatibility matrix per checkpoint

**Phase 4: Sampling & Inference (1.5-2 hours)**
- DPM++ variants: 2M, 2M Karras, SDE, impact on NSFW realism
- Euler: when preferred over DPM++, CFG sensitivity
- CFG scales: typical ranges (5.0-8.0 for NSFW), impact on anatomical detail
- Denoise ranges: quality floor (0.28), implications for LoRA weight
- Seed stability: how replicable are results across different settings?
- Negative prompt templates: NSFW-specific anti-patterns (what to avoid)

**Phase 5: Face Processing in Context (1.5-2 hours)**
- How face processing integrates into checkpoint workflow: upstream detection, mid-pipeline ReActor, downstream consistency validation
- Which face tools pair with which checkpoints (InsightFace detection + ReActor + RAFT validation)
- Multi-frame consistency: how checkpoints + face processing affect frame-to-frame stability
- Artifact detection specific to NSFW content (cum rendering artifacts, anatomy consistency)

**Phase 6: Scenario Decision Tree & Integration (2-3 hours)**
- Map scenarios to optimal configurations
- Build decision tree: scenario taxonomy → (checkpoint, LoRA stack, sampling, face processing)
- Document trade-offs per scenario (quality vs speed, realism vs style, single vs multi-frame)
- Validate with real-world examples from project history

**Phase 7: Synthesis & Report (2-3 hours)**
- Write comprehensive report covering all 5 layers
- Decision matrix: tool × criteria grid (speed, accuracy, NSFW quality, multi-frame, integration)
- Scenario playbook: decision tree formatted for easy reference
- Next steps: pilot evaluation, implementation roadmap

---

## Evaluation Criteria per Layer

### Layer 1: Checkpoints
- **Ethnicity handling:** Skin tone fidelity, proportional accuracy, expression consistency across ethnicities
- **Anatomical accuracy:** Breast anatomy (size, shape, ptosis), genital realism, body proportions
- **Explicit content quality:** Cum/fluid rendering, sexual act poses, anatomical realism in extreme angles
- **Body diversity:** Range of body types supported (curvy, petite, athletic, full), skin variations
- **Consistency:** Frame-to-frame stability (if multi-frame), seed replicability
- **Speed/efficiency:** Tokens per second, VRAM requirements, inference speed

### Layer 2: LoRAs
- **Specialization:** What does it improve? (face quality, body anatomy, specific act, photography style)
- **Checkpoint compatibility:** Works with CyberRealistic, Pony, XL, etc.?
- **Weight range:** Optimal weight (0.5-1.5), stability at different weights
- **Artifact risk:** Does it introduce glitches, anatomy errors, or degradation at high weights?
- **Stacking:** How many LoRAs can be safely stacked? Weight ceiling per category?
- **Realism impact:** Does it improve photorealism or add stylization?

### Layer 3: Sampling
- **Anatomy quality:** Does sampling choice affect anatomical detail (breast shape, genital realism)?
- **Consistency:** How stable are results? Do different seeds produce similar results with same settings?
- **Speed:** Inference time per sampler, impact on user experience
- **Artifact resistance:** Does sampler introduce glitches at certain CFG/denoise ranges?
- **Flexibility:** How sensitive is output to CFG/denoise tweaks? (responsive vs stable)
- **Negative prompt effectiveness:** How well does sampler respect negative prompts?

### Layer 4: Face Processing
- **Integration timing:** Best-placed upstream (detection), mid-pipeline (swapping), or downstream (validation)?
- **Consistency with checkpoint:** Does ReActor maintain identity across checkpoints? (CyberRealistic vs Pony vs Uber)
- **Multi-frame:** How stable is face consistency across 10+ frames?
- **Anatomical impact:** Does face processing degrade surrounding anatomy?
- **Artifact detection:** Can we quantify when face swap failed (glitch, misalignment)?
- **NSFW-specific:** How does face processing handle explicit content (exposed skin, cum, etc.)?

### Layer 5: Integration
- **Composability:** Can checkpoint + LoRAs + sampling + face processing be seamlessly combined?
- **Workflow:** How many steps (detection → swapping → validation → final output)?
- **Speed:** Total inference time for multi-step pipeline
- **Failure modes:** What breaks when stacked? (incompatible LoRA weights, face processing artifacts)
- **Reproducibility:** Given same inputs (prompt, seed, weights), do we get same output?

---

## Scenario Taxonomy

**Scenarios drive research questions:** For each scenario below, research determines the optimal checkpoint + LoRA + sampling + face processing stack.

### By Act
- **Facial** (cum, sucking, licking, gagging)
- **Anal** (insertion, progression, prolapse)
- **Oral** (blowjob, deep throat, cum in mouth)
- **Penetration** (vaginal, missionary, cowgirl, reverse cowgirl, prone)
- **Group acts** (MMF, DP, DVP, bukkake, cumswap)
- **Cumshot variants** (facial, on body, in mouth, creampie, etc.)

### By Photography/Aesthetic
- **Editorial** (clean realism, professional lighting, minimal makeup)
- **Raw** (explicit, wet, unfiltered, studio lighting)
- **Glamour** (makeup-heavy, artistic, studio, sharp focus)
- **Dark/Fetish** (noir, theatrical, conceptual, mood-driven)

### By Anatomical Focus
- **Breast detail** (size consistency, ptosis accuracy, nipple detail)
- **Cum/fluid rendering** (placement, texture, flow, interaction with body)
- **Skin tone fidelity** (ethnicity-specific undertones, consistency)
- **Anatomical accuracy** (genital realism, orifice rendering, body proportion)

### By Ethnicity & Aurora Tier
- **Fair skin** (Ukrainian, Russian, Nordic) — L1-L7 (warm lighting required), L8 (explicit body)
- **Olive/tan** (Lebanese, Persian, Spanish, Colombian) — L1-L7 (ethnicity fidelity), L8 (explicit acts)
- **Dark skin** (Ethiopian, Nigerian, Indian) — L1-L7 (skin tone + glow), L8 (body/fluid quality)
- **Tier impact** — L1-L7 prioritize ethnicity/character consistency; L8 pivots to explicit act quality

### By Character Tier (L1-L8)
- **L1-L3** (editorial, character-focused, minimal explicit)
- **L4-L7** (increasing explicitness, anatomical detail, ethnic consistency)
- **L8** (maximum explicitness, act-focused, body quality over character identity)

---

## Expected Findings (Hypotheses)

Based on project memory and community knowledge:

1. **CyberRealistic excels at:** Ethnicity fidelity (skin tones), natural proportions, consistent expressions across angles
2. **CyberRealistic gaps:** Extreme explicit poses, fluid rendering, some body diversity scenarios
3. **Uber checkpoint:** Strong for body/fluid quality, but weak on dark/medium ethnicities (golden-tan attractor)
4. **Pony:** Fantasy/stylized, but adequate for realism; good body diversity
5. **LoRA stacking:** Weight ceiling ~1.5 per category (face, body, concept) before degradation
6. **DPM++ 2M:** Industry standard for NSFW (balance of speed and quality)
7. **CFG 6.5:** Sweet spot for NSFW realism (not 7.0); denoise 0.28-0.42 for LoRA compatibility
8. **Face processing:** ReActor strong for identity lock; consistency validation (RAFT + embedding) needed downstream
9. **Multi-frame consistency:** Checkpoint affects stability more than face processing choice
10. **Scenario variation:** Different acts need different checkpoint tier (L1-L7 use CRP, L8 use Uber)

---

## Deliverables

### Primary
- `docs/research/2026-04-02-nsfw-checkpoint-ecosystem-evaluation.md` (main report)
  - Executive summary (1-2 pages) with CyberRealistic assessment + top picks per layer
  - 5 layer sections (checkpoints, LoRAs, sampling, face processing, integration)
  - Scenario playbook (decision tree mapping scenarios to configurations)
  - Scenario decision matrix (scenario × configuration grid)
  - Research notes (tools/papers/forums reviewed, limitations)

### Secondary
- `.agents/archive/research/2026-04/nsfw-checkpoint-decision-matrix.csv` (checkpoint × criteria grid)
- `.agents/archive/research/2026-04/nsfw-lora-compatibility-matrix.csv` (LoRA × checkpoint compatibility)
- `.agents/archive/research/2026-04/nsfw-scenario-playbook.csv` (scenario → checkpoint + LoRA + sampling + face processing)
- `.agents/council/nsfw-checkpoint-raw-notes.md` (raw research notes)

### Commit
- Branch: main
- Message: "docs(research): NSFW checkpoint ecosystem evaluation with scenario decision tree"

---

## Success Criteria (This Phase)

- [ ] CyberRealistic deeply evaluated: strengths, gaps, best practices documented
- [ ] 6-8 checkpoints researched with NSFW-specific scoring (ethnicity, anatomy, explicit quality)
- [ ] LoRA ecosystem catalogued: 15+ LoRAs scored per checkpoint compatibility + specialization
- [ ] Sampling methods optimized: DPM++, Euler, CFG ranges, denoise tested for NSFW realism
- [ ] Face processing integration mapped: timing, compatibility, consistency validation strategy
- [ ] Scenario decision tree complete: all 20+ scenarios mapped to optimal configurations
- [ ] 3 decision matrices created: checkpoints, LoRAs, scenarios (all CSV)
- [ ] Main report written and committed to `docs/research/`
- [ ] No TBD placeholders; all findings concrete (or explicitly flagged as "insufficient data")
- [ ] Ready for pilot evaluation or full implementation

---

## Next Steps (After This Phase)

1. **Review findings** — Read main report, scenario playbook, decision matrices
2. **Validate decision tree** — Test 3-5 scenarios on real content (optional)
3. **Identify gaps** — Are there scenarios with no good configuration? Edge cases?
4. **Implementation roadmap** — If building checkpoint selector tool or prompt optimizer, create plan
5. **Pilot evaluation** — Test recommended stacks on real NSFW generation tasks

---

## Constraints & Assumptions

- **Research only** — no code implementation
- **GitHub/HuggingFace/arXiv primary** — published tools and papers
- **NSFW-positive** — tools must work on explicit content, not degrade
- **Multi-frame aware** — consistency matters for video/sequence generation
- **Realism priority** — photorealism > stylization for NSFW use case
- **CyberRealistic anchor** — assume it's production baseline, evaluate trade-offs when deviating
- **Scenario-driven** — findings tie back to actual generation tasks from project history

---

## References & Known Context

**From project memory:**
- CyberRealistic V16 > PMP for LoRA training: natural proportions, better skin/ethnicity
- FaceDetailer denoise 0.28 = quality floor, critical for LoRA dataset consistency
- CRP (Cyber Realism Pony) = ethnicity fidelity, Uber = body/fluid quality, PMP = legacy
- L8 Uber routing: L1-L7 use CRP for ethnicity fidelity; L8 pivots to Uber for act quality
- Facial cum formula locked: realcumAI@0.60 + PornMaster-V3@0.55, weight ceilings 1.5 skin / 1.6 mouth, CFG 6.5
- ReActor vs pure generation: pure generation > ReActor for quality; ReActor only for exact identity lock
- Regional taxonomy: 4 skin-tone groups × 10 chars × 3 seeds (all successful)
- Lebanese S+ tier: Seeds 58005, 58505 confirmed S+; v3 NEG escalation (fluid NEG 1.5)

**Tools to evaluate:**
- Checkpoints: CyberRealistic, Pony, NSFW, XL, Illustrious, Z-Image, RealisticVision, PMP, Uber
- LoRAs: ReActor, face quality, regional (Lebanese, Ukrainian), body (Uber), concept (anal, cum), skill (lighting)
- Samplers: DPM++ (2M, Karras, SDE), Euler
- Face tools: InsightFace, MTCNN, ReActor, RAFT, face_recognition
- ComfyUI integration: existing nodes, custom wrappers

