# Session Retrospective — ComftyUI-Harness Governance Batch (#1–10)

**Date:** 2026-06-19  
**Branch:** feat/governance-beads-1-10 (kas1987/ComftyUI-Harness)  
**Commit:** c13167e — 17 files, 727 insertions  
**Beads closed:** mc-bcnl6, mc-dg2fo, mc-5gs33, mc-fs2rc, mc-egqay, mc-vxhij, mc-nxsn9, mc-o1uya, mc-8ikar (9 beads)

## What shipped

- `08_GOVERNANCE/CANONICAL_REPO_ROUTING.yaml` — authoritative repo identity map, alias normalization, archived fork/repo policy, routing rules
- `08_GOVERNANCE/COMFY_ALIAS_STANDARD.md` — ComftyUI vs ComfyUI alias standard; slug typo preserved (do not rename), display name normalized to "ComfyUI Harness"
- `08_GOVERNANCE/ARCHIVED_REPO_DRIFT_POLICY.md` — repo classification schema (canonical/fork/archived/deprecated), drift detection rules, impl guidance for portfolio_governance_drift.py
- `08_GOVERNANCE/CONTROL_PLANE_MIGRATION.md` — PM harness → harness-v2 migration table, telemetry discovery map, deprecated path list, cutover checklist
- `08_GOVERNANCE/MEDIA_LAB_DOCTRINE.md` — scope boundary: this repo = visual media lab, not global control plane
- `08_GOVERNANCE/VIDEO_PIPELINE_SCHEMA.yaml` — 10_VIDEO/ lane schema: run manifest, clip ledger, scoring, archive policy
- `08_GOVERNANCE/3D_MERGE_PLAN.md` — git subtree plan for merging kas1987/3D_Meta → 11_3D/
- `08_GOVERNANCE/VISUAL_ASSET_REGISTRY_SCHEMA.yaml` — asset provenance schema for all media types
- `08_GOVERNANCE/PORTFOLIO_REPO_ATLAS.md` — 6-domain ecosystem map, consolidation targets, ambiguous repo list
- `AGENTS.md` — reframed with canonical routing check, media lab identity, deprecated PM harness path warning
- `10_VIDEO/` — 7 subdirectories created with .gitkeep placeholders

## Learnings

### 1. GitHub slug typos are permanent
The repo slug `ComftyUI-Harness` contains a typo (`Comfty` instead of `Comfy`). Renaming the repo would break all existing links, issue URLs, clone commands, and CI references. The right fix is alias normalization at the governance layer — not a rename.  
**Action:** Always check if a slug is historical before proposing a rename. Document aliases in CANONICAL_REPO_ROUTING.yaml instead.

### 2. Archived repos leave ghost references in AGENTS.md
The PM harness (`ai-project-management-harness`) was archived but still referenced in AGENTS.md as the canonical control plane, including a hardcoded Windows drive path (`e:/.10_AI-project-management-harness/`). These ghost references aren't caught by grep unless you know the exact path format.  
**Action:** When archiving a repo, search all AGENTS.md files across the estate for the repo slug and the drive-letter path pattern. Update before archiving.

### 3. Media lab scope boundary prevents governance sprawl
Without explicit scope doctrine, visual-media repos accumulate governance infrastructure (routing tables, telemetry, MCP config) that belongs in the control plane. Writing MEDIA_LAB_DOCTRINE.md with an explicit IN/OUT scope table stopped this drift at the source.  
**Action:** For every repo, write scope boundary before adding governance files. "What lives here" is as important as "what lives here currently."

## KPI snapshot

| Metric | Value |
|--------|-------|
| Beads closed | 9 |
| Files created | 16 new, 1 updated |
| Lines added | 727 |
| Repos touched | 2 (ComftyUI-Harness + chromatic-harness-v2 retro) |

## Follow-up

- Open PR for `feat/governance-beads-1-10` in kas1987/ComftyUI-Harness
- mc-nxsn9 (3D merge plan) written but merge not yet executed — requires separate session with `git subtree add`
- Next bead queue: The-Veil (#22–25), fusion-computer (#18–21), ChromaticSystems (#5–12)
