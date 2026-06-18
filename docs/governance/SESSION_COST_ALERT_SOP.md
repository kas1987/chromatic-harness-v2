# Session Cost Alert SOP

> **Status:** Enforced
> **Data source:** `~/.claude/usage.db` — refreshed by `usage-sync.sh` at SessionStart
> **Trigger:** Run `usage-sync.sh` or query `usage.db` at any session boundary

## Cost Tiers

| Tier | Per-Session Cost | Meaning | Required Action |
|---|---|---|---|
| Green | $0–$10 | Normal — Sonnet/Haiku work | None |
| Amber | $10–$50 | Elevated — likely Opus or large context | Log; review at session end |
| Red | $50–$100 | High — runaway context or unauthorized Opus | Immediate review; check for loop/scan |
| Critical | $100+ | Incident — uncontrolled expansion | Halt pattern; file cost incident within 24h |

## Daily Aggregate Targets

| Metric | Target | Alert threshold |
|---|---|---|
| Daily total spend | <$500 | >$750 → Amber; >$1,500 → Red |
| Opus session count | <20/day | ≥40 → routing discipline flag |
| Single session max | <$50 | >$100 → auto-file cost incident |
| Avg cost per session | <$5 | >$10 → model mix review |

## How to Check

**Quick daily check (run after SessionStart sync):**
```bash
~/.claude/bin/usage-sync.sh --days 1
```

**Weekly review:**
```bash
sqlite3 -column ~/.claude/usage.db "
SELECT date, sessions, cost_usd,
       printf('%.0f%%', 100.0*cache_read/total_tok) AS cache
FROM daily_rollup ORDER BY date DESC LIMIT 7;"
```

**Top costly sessions (spot runaway sessions):**
```bash
sqlite3 -column ~/.claude/usage.db "
SELECT substr(session_id,1,8), model,
       printf('\$%.2f', cost_usd) AS cost,
       printf('%.0fM', total_tokens/1000000.0) AS tokens
FROM sessions
WHERE timestamp >= datetime('now','-1 day')
ORDER BY cost_usd DESC LIMIT 10;"
```

## Response Actions by Tier

### Amber ($10–$50)

1. Identify the session: check model and token breakdown.
2. Ask: was Opus authorized per `OPUS_AUTHORIZATION_GATE.md`?
3. Was context compacted at the right threshold? (target: 50–65% context pressure)
4. Note in `AGENT_RUN_LOG.jsonl`; no incident required unless recurring.

### Red ($50–$100)

1. Identify trigger: context scan, workflow loop, or deliberate deep work?
2. If scan/loop: halt the pattern; add a budget cap to the workflow.
3. If deliberate: was it authorized? If yes, note; if no, file amber incident.
4. Review `autoCompactWindow` setting — consider lowering if context balloon is the cause.
5. File `COST-YYYYMMDD-XXX` using `COST_INCIDENT_TEMPLATE.md`.

### Critical ($100+)

1. **Stop the triggering workflow or session type immediately.**
2. Identify root cause within 24h:
   - Unauthorized Opus?
   - Scan with no scope cap (no `maxFilesRead` / `maxContextTokens` in workflow)?
   - Loop without exit condition?
   - Token-heavy prompt repeated across many sub-agents?
3. File cost incident with full timeline.
4. Patch the workflow or gate before next run.
5. Add regression check to `scripts/validate_claude_harness.py`.

## Integration Points

- `usage-sync.sh` at SessionStart keeps `usage.db` current (48h window, recent transcripts only).
- `OPUS_AUTHORIZATION_GATE.md` — Amber+ sessions are often unauthorized Opus; check there first.
- `WORKFLOW_BUDGET_CONTRACT.md` — Red/Critical sessions often violate the budget class limits.
- `COST_INCIDENT_TEMPLATE.md` — use for Red/Critical write-ups.
