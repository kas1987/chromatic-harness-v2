# Legacy Repo Migration Plan

## Purpose

Preserve useful separated repos while removing stale authority claims.

## Repo Disposition

| Repo | Disposition | Action |
|---|---|---|
| `.01_Image Org` | **Harvest + retire authority** | Strip all canonical/source-of-truth claims; harvest remaining governance + scripts into Harness `docs/routing/` and `docs/governance/`; then archive. **Routing governance migrated 2026-06-02.** |
| `.04_Prism` | Harvest + demote | Remove from federation roots; harvest any unique tooling into Harness; mark as legacy parent workspace |
| `Chromatic_Brain` | Migrate/archive | Convert queue/planning items into GitHub issues/beads; mark as legacy brain archive |
| `claude-config` | Demote/adapt | Keep slash commands and config, remove independent orchestration logic |
| `ChromaticSystems` | Federate | Keep registries; sync skill and governance summaries into Harness |
| `chromatic-wiki` | Promote canon | Keep durable knowledge only; consume promoted artifacts |
| `chromatic-stack` | Keep substrate | Keep service definitions; expose machine-readable service registry |

> **Authority principle:** `chromatic-harness-v2` is the single canonical home for routing/governance.
> Legacy repos contribute knowledge (harvested into Harness or the wiki) but hold **no** live authority.
> Federation is one-way: Harness `docs/routing/` → `~/.claude/governance/`, `~/.agents/governance/`,
> `chromatic-wiki/03_GOVERNANCE/` via `scripts/federate-governance.sh`. Never edit federated copies.

## Migration Steps

### .01_Image Org  *(priority — was the largest stale-authority source)*

**Done (2026-06-02):**
1. ✅ Routing governance migrated to Harness `docs/routing/`: `multi-router-matrix.yaml`, `auto-mode-scope.yaml`, `subagent-token-efficiency.md`, `model-routing-for-subagents.md`.
2. ✅ Federation re-pointed: canonical is Harness; `~/.claude/governance/` + `~/.agents/governance/` now marked "federated copy"; `scripts/federate-governance.sh` syncs them + the wiki.
3. ✅ Stripped `C:\.01_Image Org` from federation roots in the migrated files.
4. ✅ Removed hardcoded `cd "C:\.01_Image Org"` from `~/.claude/scheduled-tasks/{weekly-skills-reflection,worktree-tooling-sweep}/SKILL.md`.

**Remaining:**
1. Scan `.01_Image Org` for any other live authority (`pnpm run governance:*:federate` scripts, `.agents/governance/` originals) and neutralize — point them at the Harness or delete.
2. Harvest durable knowledge (retros, learnings, specs) into `chromatic-wiki`; discard duplicates.
3. Clean residual refs in `~/.claude/.bin/ao.sh` (WSL fallback path) and `~/.claude/docs/operations/MULTI-ROUTER-MATRIX.md`.
4. Update `.01_Image Org/README`: "Legacy archive; no execution authority. See chromatic-harness-v2."
5. Archive the repo (org-move or mark read-only) once harvest confirms nothing live remains.

### Chromatic_Brain

1. Inventory active queue items.
2. Classify each item as migrate, archive, duplicate, or obsolete.
3. Convert migrate items into GitHub issues or beads.
4. Update README: "Legacy planning archive; not execution authority."
5. Add pointer to Harness v2 queue/governance.

### claude-config

1. Add adapter policy.
2. Replace decision logic with script calls.
3. Mark routing docs as historical where Harness v2 supersedes them.
4. Add command matrix pointing to Harness scripts.

### ChromaticSystems

1. Keep skill catalog and prune plan.
2. Add generated summary export for Harness v2.
3. Define canonical skill source policy.
4. Wire skill catalog into Harness health/readiness checks.

### chromatic-wiki

1. Keep canon/promotion flow.
2. Add latest Harness v2 governance references.
3. Add "not runtime" warning to policies that could be mistaken for active gates.

### chromatic-stack

1. Export service registry.
2. Sync service list into Harness health check configuration.
3. Add security/auth posture per service.
