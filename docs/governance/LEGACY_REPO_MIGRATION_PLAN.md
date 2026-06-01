# Legacy Repo Migration Plan

## Purpose

Preserve useful separated repos while removing stale authority claims.

## Repo Disposition

| Repo | Disposition | Action |
|---|---|---|
| `Chromatic_Brain` | Migrate/archive | Convert queue/planning items into GitHub issues/beads; mark as legacy brain archive |
| `claude-config` | Demote/adapt | Keep slash commands and config, remove independent orchestration logic |
| `ChromaticSystems` | Federate | Keep registries; sync skill and governance summaries into Harness |
| `chromatic-wiki` | Promote canon | Keep durable knowledge only; consume promoted artifacts |
| `chromatic-stack` | Keep substrate | Keep service definitions; expose machine-readable service registry |

## Migration Steps

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
