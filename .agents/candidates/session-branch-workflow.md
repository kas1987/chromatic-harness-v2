---
name: session-branch-workflow
source_ids: [2026-05-02-session-branch-workflow]
source_type: pattern
confidence: 0.90
suggested_use: Start Sessions on Named Branches
canon_map: general
status: approved
tags: []
---

## Summary

Start Sessions on Named Branches

## Evidence

# Learning: Start Sessions on Named Branches

## What We Learned

`~/.claude/bin/start-session.sh [topic]` cuts a `session/YYYY-MM-DD-topic` branch from master (after pulling) and should be the standard session opener for claude-config work. A pre-push hook blocks accidental direct pushes to master.

Usage:
```bash
bash ~/.claude/bin/start-session.sh hook-audit   # → session/2026-05-02-hook-audit
# when done:
gh pr create --draft --repo kas1987/claude-config
```

## Why It Matters

Keeps master clean; each session's changes are reviewable as a PR diff rather than accumulating directly on master.

## Source

Added in commit e53c62f, 2026-05-02.
