# Pattern Frontmatter Schema

Files in `.agents/patterns/` follow this frontmatter schema:

```yaml
---
name: short-kebab-case-slug
type: pattern | anti-pattern | principle
confidence: 0.0-1.0
source_learnings: [learning-slug-1, learning-slug-2]
description: one-line summary
tags: [tag1, tag2]
---
Body: what this pattern is, when to apply it, evidence.
```

## Field Definitions

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | kebab-case slug, unique within type |
| `type` | enum | yes | `pattern`, `anti-pattern`, or `principle` |
| `confidence` | float | yes | 0.0–1.0, inherited from source learnings (max) |
| `source_learnings` | list[str] | yes | slugs of `.agents/learnings/` files that contributed |
| `description` | string | yes | one-line summary |
| `tags` | list[str] | no | inherited from source learnings, deduplicated |

## Classification Heuristics

`extract_patterns.py` classifies each learning by scanning body + description for keywords:

- **anti-pattern**: "avoid", "don't", "never", "bad", "harmful", "wrong", "mistake"
- **principle**: "always", "rule:", "principle:", "invariant", "must"
- **pattern**: everything else

Source file: `scripts/extract_patterns.py`
