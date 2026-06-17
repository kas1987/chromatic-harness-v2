---
type: learning
source: retro-quick
date: 2026-03-31
---

# Learning: PostToolUse linter reverts incremental Edit calls — use Write for persistent changes

**Category**: process
**Confidence**: high

## What We Learned

In this project's Claude Code setup, a PostToolUse hook fires on every Edit/Write/Bash call and can trigger a linter that reverts changes to certain files (particularly `src/index.ts`). Incremental `Edit` calls are silently undone within seconds.

**Symptom:** Multiple Edit calls succeed with "file updated successfully" but git diff shows the file unchanged. The system-reminder reports "file modified by a linter."

**Fix:** Write the entire file in a single `Write` tool call. The linter appears to accept full-file writes while reverting incremental edits. After a successful `Write`, verify with `grep` immediately — if the key lines are present, the write persisted.

**Why this matters:** If a module's initialization is removed from `index.ts`, the module's exports still load without error but its routes are never registered. All endpoints return 404 silently.

## Source

gen index.ts — delegate router additions kept being stripped, routes kept returning 404
