---
id: research-2026-05-24-in-review-pipeline
type: research
date: 2026-05-24
---

# Research: Automated "In Review" Pipeline

**Backend:** claude-native-teams
**Scope:** Multica webhook/autopilot capabilities, hook chain, git tooling, router matrix for review

## Summary

Multica already supports autopilots with webhook triggers and agents do move issues to `in_review` (seen in MET-2, MET-3 daemon logs). The router matrix already classifies code review at tier 2 (gpt-4o-mini). The missing pieces are: a status watcher that fires when issues enter `in_review`, a multi-tier review orchestrator skill, a session packager, and an auto-push gate. All gaps are buildable with existing infrastructure.

## Key Files

| File | Purpose |
|------|---------|
| `~/.claude/hooks/multica-notify.sh` | PostToolUse Agent hook — currently only sets `in_progress` |
| `~/.claude/hooks/model-router.sh` | PreToolUse Agent hook — 5-tier LLM routing |
| `~/.claude/config/router-patterns.json` | Tier classification patterns (tier 2 = code review) |
| `~/.claude/config/provider-tiers.json` | Tier → provider/model mapping |
| `~/.claude/hooks/pre-push.sh` | Blocks master pushes, enforces session/* branches |
| `~/.claude/bin/start-session.sh` | Creates session/YYYY-MM-DD-topic branches |
| `~/.multica/config.json` | Multica workspace config and token |
| `~/.multica/daemon.log` | Daemon WebSocket events, task lifecycle |

## Findings

### What exists
- `multica issue update <id> --status in_review` — works, agents call it
- `multica autopilot trigger-add <id> --kind webhook` — creates callable webhook URL
- Daemon uses WebSocket (heartbeat every ~10s); no `issue watch` CLI mode
- Router tier 2 pattern: "code quality review, spec compliance, single-file review" → gpt-4o-mini
- `start-session.sh` creates `session/YYYY-MM-DD-topic` branches; pre-push runs E2E gates
- Three existing autopilots (Hook Audit, Skill Forge, Knowledge Harvest) — none triggered

### What's missing
1. **Status watcher** — nothing polls/subscribes to `in_review` transitions
2. **Review orchestrator** — no skill dispatches tiered LLM review based on issue complexity
3. **Session packager** — no tool bundles diff + test results + review summary
4. **Auto-commit/push** — no hook wires review pass → git commit → push → (optional) merge
5. **multica-notify.sh gap** — only writes `in_progress`, doesn't move to `in_review` on agent completion

### Router alignment for review tasks
- Tier 2 (gpt-4o-mini): single-file review, spec compliance — handles ~70% of tasks
- Tier 3 (gemini-2.5-flash): multi-file, cross-module — handles complex refactors
- Tier 4 (claude-sonnet): architecture review, novel patterns — reserved for T4 tasks only

### Build plan constraints (from harness)
- Never push to master — always session/* branch
- Never commit raw API keys
- Hook chain must not break — model-router.sh stays first in PreToolUse[Agent]
- T1-T3 work fully autonomous; T4 confirmation required

## Recommendations

1. **`~/.claude/hooks/in-review-watcher.sh`** — poll `multica issue list --status in_review`, fire review for new items (run via SessionStart cron or multica autopilot)
2. **`~/.claude/skills/review-orchestrator/`** — skill: read issue → score complexity → dispatch tier 2/3/4 reviewer → collect result → post comment → update status
3. **`~/.claude/hooks/session-packager.sh`** — on review PASS: `git diff HEAD`, collect test results, write summary to `.agents/review/YYYY-MM-DD-<issue>.md`
4. **`~/.claude/hooks/auto-push.sh`** — after packager: auto-commit deliverable, push to session branch, optionally `gh pr create --draft`
5. **Update `multica-notify.sh`** — detect agent task completion (not just start) and move issue to `in_review`
6. **Multica "Review" autopilot** — webhook-triggered autopilot that creates a review issue assigned to Claude Orchestrator
