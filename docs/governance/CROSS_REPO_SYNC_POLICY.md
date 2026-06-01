# Cross-Repo Sync Policy

## Purpose

Define how Chromatic repos exchange durable knowledge, service definitions, skills, and operational state without creating duplicate authorities.

## Sync Classes

| Class | Direction | Example | Authority |
|---|---|---|---|
| Promotion | Harness -> Wiki | Stable playbook | Wiki after review |
| Infrastructure sync | Stack -> Harness | Service endpoint list | Stack defines, Harness checks |
| Adapter sync | Harness -> Claude Config | Slash command target scripts | Harness owns behavior |
| Migration sync | Brain -> Harness | Legacy queue item | Harness owns active work |
| Registry sync | Systems -> Harness | Skill catalog summary | Systems catalogs, Harness validates |

## Rules

1. Sync must declare source and target.
2. Sync must not overwrite an authority repo with an adapter repo.
3. Sync must preserve provenance.
4. Runtime state should not be copied into Wiki unless reviewed.
5. Legacy queue items must be converted into GitHub issues/beads before execution.
6. Service endpoints from Stack must be validated by Harness health checks.
7. Claude commands must call Harness scripts instead of duplicating logic.

## Required Metadata

Every cross-repo sync artifact should include:

```yaml
source_repo: ""
target_repo: ""
domain: ""
authority_repo: ""
sync_direction: ""
provenance: ""
review_required: true
last_synced_at: ""
```

## Drift Detection

A drift exists when:

- two repos claim authority over the same domain;
- an adapter contains duplicated decision logic;
- a legacy queue has active non-migrated items;
- Wiki canon conflicts with current Harness governance;
- Stack service definitions do not match Harness health checks;
- skill catalog counts diverge without an explanation.
