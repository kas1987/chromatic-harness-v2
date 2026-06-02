# Beads Playbook

## Purpose

Defines how findings, alerts, failures, and next actions become Beads.

## Creation Sources

- Magnet report
- Agent Lead report
- failed validation
- missed inflection point
- user request
- PDR action item
- reviewer finding

## Priority Rules

| Priority | Meaning |
|---|---|
| p0 | safety, destructive risk, data loss, production breakage |
| p1 | core project progress or critical dependency |
| p2 | important improvement |
| p3 | backlog or optional exploration |

## Creating Beads & Epics

Templates (copy → fill → create): [`templates/EPIC_TEMPLATE.md`](../templates/EPIC_TEMPLATE.md),
[`templates/BEAD_TEMPLATE.md`](../templates/BEAD_TEMPLATE.md). Full map:
[`CHROMATIC_TREES.md` §5/§6](../CHROMATIC_TREES.md#6-creating-work--recipes).

```bash
# Epic (work stream)
bd create "<area>: <title>" --type epic -p P1 -l <area-label> \
  -d "<summary>" --acceptance "<observable close criteria>" --silent   # prints epic id

# Bead (one artifact + its tests, under an epic)
bd create "<title>" --type task -p P2 --parent <epic-id> -l <area-label> -d "<scope>"

# Persist (the .beads/issues.jsonl export is passive)
bd dolt commit && bd dolt push
```

**Rules:** one bead = one artifact + tests · always `--parent` a bead to its epic ·
label every v-program bead with the program label (e.g. `v3`) for `bd list --label <prog>`.

## Lifecycle

```bash
bd ready                 # pick next work — never from chat
bd update <id> --claim   # or --status in_progress
bd show <id>
bd close <id> --reason "<what shipped>"
```
