# Candidate Frontmatter Schema

Candidate records live in `.agents/candidates/` and represent items formally staged
for review before promotion to the Chromatic Wiki.

## Frontmatter Fields

```yaml
---
name: short-kebab-case-slug
source_ids: [learning-slug-or-pattern-slug, ...]
source_type: learning | pattern | principle
confidence: 0.0-1.0
suggested_use: one-line description of where/how to apply
canon_map: general | routing | security | knowledge | operations
status: pending | approved | rejected
tags: [tag1, tag2]
---
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Unique kebab-case slug matching the source pattern/learning name |
| `source_ids` | list | yes | Slug(s) of source learning or pattern file(s) |
| `source_type` | enum | yes | `learning`, `pattern`, or `principle` |
| `confidence` | float | yes | 0.0–1.0 confidence score from source artifact |
| `suggested_use` | string | yes | One-line description of where/how to apply this knowledge |
| `canon_map` | enum | yes | Knowledge domain: `general`, `routing`, `security`, `knowledge`, `operations` |
| `status` | enum | yes | Workflow state: `pending`, `approved`, or `rejected` |
| `tags` | list | no | Inherited or additional classification tags |

## Body Format

```markdown
## Summary
What this candidate captures and why it matters.

## Evidence
Source(s), confidence rationale, observed pattern frequency.

## When to Apply
Concrete conditions under which this guidance applies.
```

## Workflow

1. `stage_candidates.py` — auto-generates `pending` records from patterns with confidence >= 0.7
2. Human review — edit `status: approved` or `status: rejected`
3. `promote_to_wiki.py` — only promotes items with `status: approved`
