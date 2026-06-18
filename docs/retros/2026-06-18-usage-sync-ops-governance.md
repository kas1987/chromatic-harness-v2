# Session Retrospective — usage-sync wiring + OPS governance SOPs

**Date:** 2026-06-18
**PRs merged:** none
**Epics closed:** none (ad-hoc governance work)

## What shipped

- **`usage-sync.sh` SessionStart hook** wired into `~/.claude/settings.json` — fires at each session start, scans 48h of transcripts, UPSERTs into `usage.db`. First run synced 789 sessions cleanly (exit 0).
- **`OPUS_AUTHORIZATION_GATE.md`** — explicit allow-list for Opus dispatch; default-deny to Sonnet; targets Opus from 89% → <30% of spend.
- **`SESSION_COST_ALERT_SOP.md`** — Green/Amber/Red/Critical tiers ($10/$50/$100/session); daily aggregate targets; sqlite queries for each tier review.
- **`CACHE_HEALTH_SOP.md`** — system prompt freeze policy; Haiku session consolidation rules (batch ≥3 tasks, target ≥50 API calls/session); compaction floor at 65% context pressure.
- **`00_WORKFLOW_GOVERNANCE.md`** updated with Cost & Model Governance section linking the three new SOPs.

## Learnings

### 1. Glob tool silently misses files in hidden directories on Windows
`Glob("bin/*.sh", path="C:\Users\kas41\.claude")` returned no results even though `usage-sync.sh` existed at that path. `Grep` and `PowerShell Test-Path` both found it correctly.
**Action:** Never conclude a file is missing from Glob alone in a `.`-prefixed directory on Windows. Verify with `Grep` or `PowerShell Test-Path` before taking remediation action.

### 2. 96% cache-read is near the theoretical ceiling — don't try to push it much further
The 4% cache-creation share is mandatory overhead to build cache blocks. You cannot have cache reads without cache writes. Trying to eliminate that 4% would require eliminating caching entirely.
**Action:** Cache-health monitoring should alert on drops below 93%, not target above 98%. Focus optimization effort on Haiku (85%) and model routing, not Sonnet/Opus cache rate.

### 3. Opus was running at near-parity with Sonnet despite Sonnet-first governance
146 Opus vs 125 Sonnet sessions over 2 days = 89% of spend from Opus ($2,442 vs $304). `MODEL_ROUTING_RULES.md` already specified Sonnet-first — the rule existed but the gate didn't.
**Action:** Written policies without enforcement hooks are decorative. `OPUS_AUTHORIZATION_GATE.md` is the policy; the next step is wiring it into `model-router.sh`.

### 4. AI-generated advice about WSL2 networking was a misdirection
The presented advice suggested `/mnt/c/` paths and a full Claude Code reinstall for a "missing" script. Both wrong for this environment (Git Bash uses `/c/`; the script existed). The WSL2 mirrored networking warning was informational noise, not a root cause.
**Action:** Cross-reference any external AI diagnostic advice against known environment facts before acting. Check the actual file system before assuming a file is missing.

## KPI snapshot

| KPI | Value (2026-06-16/17 actuals) |
|---|---|
| Daily spend | $1,252 / $1,488 |
| Cache-read rate (Opus/Sonnet) | 96% |
| Cache-read rate (Haiku) | 85% |
| Opus share of spend | 89% ($2,442 / $2,749) |
| Opus avg cost/session | $16.73 |
| Sonnet avg cost/session | $2.43 |
| Haiku avg cost/session | $0.23 |
| Opus sessions/day | ~73 |
| Sonnet sessions/day | ~63 |
| Haiku sessions/day | ~6 |

## Follow-up

- Wire `OPUS_AUTHORIZATION_GATE.md` enforcement into `model-router.sh` (PreToolUse Agent hook) — currently advisory only
- Haiku session consolidation: identify which task types are spawning short Haiku sessions and batch them
- Re-check cache-read in 7 days after system prompt freeze policy takes effect
- Next bead: `bd ready`
