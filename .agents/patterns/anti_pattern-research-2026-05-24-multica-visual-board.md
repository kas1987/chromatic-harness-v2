---
name: research-2026-05-24-multica-visual-board
type: anti-pattern
confidence: 0.50
source_learnings: [2026-05-24-multica-visual-board]
description: Research: Multica Visual Board Dashboard
tags: []
---

# Research: Multica Visual Board Dashboard

**Backend:** inline
**Scope:** Multica REST API capabilities, data model, single-file dashboard feasibility

## Summary

Multica exposes a REST API at `https://api.multica.ai/api` accessible with the bearer token from `~/.multica/config.json`. All required data — issues with hierarchy, agent assignments, comments with review content, status transitions — is available via polling. A single self-contained HTML file can implement the full visual board experience with no build tools.

## Key Files / Endpoints

| Resource | Endpoint | Key Fields |
|----------|----------|------------|
| Issues | `GET /api/issues?workspace_id={id}` | id, identifier, title, description, status, parent_issue_id, assignee_id, assignee_type, priority, metadata, labels, updated_at |
| Comments | `GET /api/issues/{id}/comments?workspace_id={id}` | content, author_id, author_type, created_at |
| Agents | `GET /api/agents?workspace_id={id}` | id, name |
| Autopilots | `GET /api/autopilots?workspace_id={id}` | id, title, status, execution_mode |

## Findings

### Data model for hierarchy (Master Card)
- `parent_issue_id` is already on every issue — child issues point to their master
- A "Master Card" = any issue that has at least one other issue with `parent_issue_id == this.id`
- Progress ring = `(done_children / total_children) * 100`

### Status flow (board columns)
`todo` → `in_progress` → `in_review` → `done`
- Each status maps to a board column
- Real-time via 5s polling (no WebSocket subscription needed from browser)

### Review metadata in comments
- Review tier and verdict visible in comment content (`**Auto-Review (Tier 2 / gpt-4o-mini):** PASS`)
- Can parse tier and verdict from comment content pattern

### API auth
- Token: `mul_82b6d4ceb07fe6ffa6ece33e25f20448286e4754`
- Workspace: `9c0b3cef-7bc4-4d93-bbd3-bc56b7cfc9bf`
- Both can be embedded in the HTML since it's local-only

## Recommendations

**Build `~/.claude/multica-board.html`** — single self-contained HTML file:
1. **Polling engine** — `fetch()` every 5s, diff against prior state for animations
2. **Column layout** — CSS Grid, 4 columns (Todo / In Progress / In Review / Done)
3. **Card states** — status-colored borders, pulsing amber for in_progress, collapsing done cards
4. **Master card** — groups children, SVG progress ring, glows green on full completion
5. **Popout drawer** — right-side slide panel with full details, comments, agent badge, review tier
6. **Animations** — CSS keyframes for state transitions, card entry/exit
- No framework, no build step, opens directly in browser
- Hardcode token + workspace ID (local dashboard, not published)
