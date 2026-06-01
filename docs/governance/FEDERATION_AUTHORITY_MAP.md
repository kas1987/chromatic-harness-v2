# Federation Authority Map

## Core Rule

`chromatic-harness-v2` is the active execution authority. Other Chromatic repos are federated support systems.

## Authority Table

| Domain | Authority Repo | Supporting Repos | Notes |
|---|---|---|---|
| Runtime execution | `chromatic-harness-v2` | `claude-config` | Claude only adapts into Harness scripts |
| Queue / work dispatch | `chromatic-harness-v2` | `Command-Center`, `Chromatic_Brain` | Brain queue is legacy/migration source |
| CI / governance gates | `chromatic-harness-v2` | `ChromaticSystems` | Systems may hold standards/catalogs |
| Durable canon | `chromatic-wiki` | `chromatic-harness-v2` | Wiki receives promoted material only |
| Local services | `chromatic-stack` | `chromatic-harness-v2` | Stack defines services; Harness checks health |
| Claude behavior | `claude-config` | `chromatic-harness-v2` | Adapter-only, no independent orchestration |
| Skill registry | `ChromaticSystems` | `chromatic-harness-v2`, `Chromatic_Skills` | Systems catalogs; Harness validates runtime usage |
| Legacy planning | `Chromatic_Brain` | `chromatic-harness-v2` | Archive/migration source only |

## Prohibited Authority Collisions

A repo must not claim authority over a domain assigned to another repo unless it is explicitly marked as a supporting or adapter repo.

Examples:

- `Chromatic_Brain` must not claim active queue authority.
- `claude-config` must not claim shipping authority.
- `chromatic-wiki` must not claim runtime execution authority.
- `chromatic-stack` must not decide GO/NO-GO release readiness.
- `ChromaticSystems` must not enforce runtime behavior outside Harness v2 gates.

## Promotion Flow

```text
Harness runtime evidence
  -> learning bead / decision log / governance artifact
  -> canon candidate
  -> Wiki durable doc
  -> optional registry update
```

## Demotion Flow

```text
Old source-of-truth claim
  -> identify domain conflict
  -> update README/frontmatter
  -> convert old logic to adapter/reference/archive
  -> add migration item if useful
```
