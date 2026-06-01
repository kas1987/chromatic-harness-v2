# Skill Registry Federation Plan

## Purpose

Make `ChromaticSystems` the skill catalog/registry source while letting `chromatic-harness-v2` enforce runtime skill health.

## Current Problem

Skill inventories can exist across workstation, repo, Claude, Codex, Cursor, Prism, Brain, and Systems surfaces. Without federation, duplicate skills and stale skills accumulate.

## Target Model

```text
ChromaticSystems
  -> skill catalog
  -> duplicate/prune plan
  -> canonical skill source map
  -> Harness v2 skill health summary
  -> Harness health/readiness gates
```

## Required Exports

From `ChromaticSystems`:

```text
09_REGISTRY/skill-catalog.json
09_REGISTRY/skill-prune-plan.json
09_REGISTRY/skill-scope-map.json
```

Into `chromatic-harness-v2`:

```text
reports/skill_registry/latest.json
reports/skill_registry/latest.md
```

## Acceptance Criteria

- [ ] Harness can read a generated skill registry summary.
- [ ] Duplicate groups are reported.
- [ ] Archive candidates are counted.
- [ ] Canonical skill sources are visible.
- [ ] No runtime skill is used without a discoverable `SKILL.md`.
- [ ] Deprecated skills are not invoked by GO-mode.
