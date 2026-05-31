---
name: phase7-agent-registration
type: anti-pattern
confidence: 0.90
source_learnings: [2026-05-28-phase7-agent-registration]
description: Learning: Props-Lift Polling Components Before Adding a Second Data Source
tags: []
---

# Learning: Props-Lift Polling Components Before Adding a Second Data Source

## What We Learned

When a self-fetching component (`AgentProfiles` polling via `setInterval`) needs to share state with a sibling (`AgentRegistration`), the correct fix is to lift state into the parent page — not to add a callback between siblings. Extracting `getAgents()` into the page's existing refresh loop and passing `agents/selectedAgent/onSelect` as props eliminated the dual-poll race in a single refactor step.

## Why It Matters

Sibling-state sharing via callbacks or context adds indirection; props-lifting is zero-cost and keeps the data flow visible in one place.

## Source

Phase 7 Agent Registration + AgentProfiles refactor (commit 74ad825).

---

# Learning: Read Before Every Edit, Re-Read After Formatter-Triggering Edits

## What We Learned

The PostToolUse formatter hook modifies files immediately after any Edit. If a second Edit targets a region the formatter reformatted, the `old_string` match fails. The reliable pattern is: Read → Edit → (formatter fires) → Read again → next Edit. A "file has not been read yet" error on the first Edit of a session is always avoidable by reading first.

## Why It Matters

Skipping the Read adds a round-trip error that breaks edit sequences and wastes context on the retry.

## Source

Repeated during Phase 7 (models.py, main.py Edit failures).

---

# Learning: Absolute-Positioned Children in Flex Containers Resolve to the Wrong Ancestor

## What We Learned

`position: absolute` on a child of `display: flex` resolves to the nearest ancestor with `position: relative/absolute/fixed/sticky` — which may be the page root, not the flex row. The connector line in `AgentRegistration.tsx`'s L0-L5 rail uses this pattern without `position: relative` on the parent, causing visual misalignment at non-standard widths.

## Why It Matters

This is a silent CSS footgun — it looks correct in Chromium at standard viewport widths but breaks at other sizes or zoom levels. Always add `position: relative` to the flex parent when mixing absolute children.

## Source

TD-2 finding from Phase 7 post-mortem council, AgentRegistration.tsx promotion timeline rail.
