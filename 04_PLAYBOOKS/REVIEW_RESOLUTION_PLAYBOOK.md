# Review Resolution Playbook

## Purpose

Ensure every agent fix is proven back to the PR with evidence.

## Required Resolution Comment

```md
## Chromatic Review Resolution

**Finding:** RF-...
**Queue Item:** NW-...
**Status:** Resolved / Blocked / Needs Reviewer Clarification
**Agent:** Sentinel
**Confidence:** 86/100

### Change made
...

### Validation
- `pytest ...`
- `ruff check ...`

### Files changed
- `path/to/file`

### Notes
...
```

## Rules

1. Do not mark a finding resolved without validation or a documented reason.
2. If tests fail outside touched scope, mark blocked and create follow-up.
3. If reviewer intent is unclear, ask clarification instead of guessing.
4. Update resolution logs after commenting.
