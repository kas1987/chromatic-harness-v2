# Chromatic/Prism Estate Audit — Fit for the Harness

**Date:** 2026-06-02 · **Harness:** `chromatic-harness-v2` (Visual Control Plane scaffold) · **Manifest:** [`estate.repos.json`](./estate.repos.json)

The harness is a portable control-plane scaffold *installed into* estate repos
(`scripts/install_visual_control_plane.py --target <repo>`). For it to manage the
estate reliably, the estate must have **one home, uniform branches, and a
machine-readable membership list**. This audit establishes that.

## Inventory
- **38 repos** across two identities: `kas1987` (32) and `Poly-Chromatic` org (6).
- The org repo `Poly-Chromatic/poly-chromatic` is the designated **governance parent**
  (governance, specs, ChromaticTrees) — but most estate repos live under personal `kas1987`.
- `~/.claude/governance/auto-mode-scope.yaml` defined the estate as only 5 federation
  roots; the other 33 repos had **no membership marker**. `estate.repos.json` fixes this.

## Reconciliation with the prior plan (IMPORTANT)
A tiered plan **already existed**: `Poly-Chromatic/chromatic-command-center:CHROMATIC_REPO_CONSOLIDATION_MAP.md`
**v0.5.0 (2026-05-25)**. Decision (2026-06-02): **adopt it as the source of truth**;
`estate.repos.json` v2.0.0 is now its machine-readable, drift-refreshed form. The earlier
"consolidate everything into Poly-Chromatic" framing is **superseded** — the plan keeps a
deliberate **5-canonical split**:

| Canonical | Owner | Role |
|---|---|---|
| `chromatic-command-center` | Poly-Chromatic | Portfolio command hub |
| `prism-autonomy-harness` | Poly-Chromatic | Autonomy runtime |
| `ChromaticSystems` | kas1987 | Governance & standards |
| `fusion-computer` | kas1987 | Artifact factory |
| `The-Veil` | kas1987 | Creative IP flagship |

Tiers 2–3 are already DONE (Command-Center → `ARCHIVED_REDIRECT`, agentops → autonomy subsystem, etc).
Guardrails carried over: **archive before delete; no deletes until tier 5; no force-push; no secret movement.**

## Decisions (2026-06-02)
1. **Adopt the v0.5.0 tiered plan**; manifest = its refreshed machine-readable form (5-canonical split, not flat-org).
2. **Keep the harness PUBLIC** as a shareable scaffold — harden instead of hide.
3. **Canonical default branch = `main`** for every estate repo.
4. **`Image-Org`** — v0.5.0 classified it `STANDALONE_EXTERNAL` (third-party Image MetaHub fork, MPL-2.0).
   User override 2026-06-02: **retire & delete** anyway; knowledge harvested to `chromatic-wiki` (wiki PR #25).

## Doctrine: keep the harness clean; legacy repos → wiki → retire
- **The harness is the control plane, not a content store.** Do NOT migrate legacy repo
  contents into `chromatic-harness-v2`. Keep it minimal.
- **Stop using legacy repos** (`Image-Org` and other `role: retire` repos). They are not
  active; the default assumption is that *little* in them is worth keeping.
- **Migration flow:** `harvest-code → preserve-knowledge-to-wiki → archive → delete`.
  Take only the small amount of still-valuable code into the canonical target repo;
  preserve decisions/learnings/docs into **`chromatic-wiki`** (the estate knowledge base);
  then archive and delete the source. Per-repo `harvest_target` in the manifest names the destination.

## Done in this change
- ✅ Created `main` on `chromatic-harness-v2` from the de-facto trunk
  (`session/chromatic-harness-v2-initial`, which already contained merged PR #203) and
  set it as the remote **default branch**. (Previously the default was a throwaway session branch.)
- ✅ Activated the existing pre-commit secret gate (`git_hooks/pre-commit` →
  `scan_for_secrets.py --staged`) via `core.hooksPath=git_hooks`. Closes the wiring gap
  behind **OBS-009**. CI already runs the blocking secret scan; commit-time was the gap.
- ✅ Added the machine-readable estate manifest + schema (this directory).

## High-priority follow-ups (outward-facing — require approval)
| Action | Why | Risk |
|---|---|---|
| Fix `poly-chromatic` default branch `feat/chromatic-harness-sprint-01` → `main` | It's the **governance root** and has the same anti-pattern the harness just had | Low, reversible |
| Move estate-member repos to `Poly-Chromatic` (see manifest `target_home`) | One governed home for the harness to manage | Breaks old URLs (GitHub redirects); preserves issues/stars |
| Delete `Master_CCC` (1.79 GB archived), `Chromatic_Audit` (empty), `JOB`, `kas1987/prism-autonomy-harness` (archived dup) | Dead weight / duplicates | **Irreversible** |
| Fold `Command-Center`→`chromatic-command-center`, verify `Image-Org` vs `Image-Prism` | Resolve duplicate pairs | Medium |
| Prune ~70 stale branches on the harness (`chore/j2r0-*`, merged `clean/*`) | Branch sprawl | Low (delete merged only) |

## Branch-name normalization needed (`Main`/`Master`/feature → `main`)
`Poly-Chromatic/poly-chromatic` (feature branch), `Poly-Chromatic/prism-autonomy-harness` (Main),
`3D_Meta` (Main), `Chromatic_Skills` (Main), `Viel-Small-Town` (Main), `agentops` (Main),
`04-prism-LAP` (preserve/* branch), plus several `master` repos. See manifest per-repo `action`.

## Security
The PUBLIC harness tracks a **scrubbed** `.claude/settings.json` (no live token found in the
committed copy — `scrub-settings-secrets.py` sanitizes it). The pre-commit gate above is the
safeguard against a future accidental token commit. Separately tracked: the pending
`GH_TOKEN` rotation T4 for `kas1987/claude-config` (leaked `gho_` in history).
