# Cache Health SOP

> **Status:** Enforced
> **Baseline (2026-06-16/17):** Opus/Sonnet = 96% cache-read; Haiku = 85% cache-read
> **Target:** Opus/Sonnet ≥ 96% (hold); Haiku ≥ 90%

## Why Cache Matters

At current Sonnet pricing:
- Cache-read token: $0.30/M  # pragma: allowlist secret
- Fresh input token: $3.00/M (10× more expensive)  # pragma: allowlist secret
- Cache-creation token: $3.75/M (one-time cost to build the block)  # pragma: allowlist secret

96% cache-read on a 1B-token day means ~$288 in cache reads vs ~$2,880 if uncached.
Every point of cache-read lost shifts tokens from the cheap bucket to the expensive one.

## System Prompt Freeze Policy

**System prompts are immutable between sessions.** Any change invalidates all existing
cache blocks for that model+context combination, forcing a full re-creation pass.

Rules:
1. System prompts are versioned in `docs/governance/` or `scripts/` — never edited inline.
2. A system prompt change requires a version bump (e.g., `SYSTEM_PROMPT_v2.md`) and a
   comment noting the cache cost: `# cache invalidation: ~Xk tokens × $3.75/M`.
3. Session hooks and dynamic injections must be appended **after** the stable frozen block,
   not inserted into it.
4. Test prompt changes in a throwaway session before rolling out — confirm cache_creation
   in `usage.db` returns to baseline within 2 sessions.

## Haiku Session Consolidation Rules

Haiku's 85% cache-read (vs 96% for larger models) reflects short sessions that create
cache blocks but don't read them enough times to amortize. Fix: batch, don't scatter.

| Rule | Detail |
|---|---|
| Minimum task batch | Don't spawn a Haiku agent for a single small task. Batch ≥3 related leaf tasks per session. |
| Session length target | Target ≥50 API calls per Haiku session before closing (currently averaging ~10). |
| Avoid cold starts | Reuse an existing Haiku session for the same task type rather than opening a new one. |
| Scope similarity | Group tasks with similar system prompts — they share cache blocks. |

## Cache Kill Patterns — Avoid These

| Pattern | Why it kills cache | Fix |
|---|---|---|
| Rewriting the system prompt each session | Invalidates all blocks | Freeze the prompt (see above) |
| Many short Haiku sessions | Creates blocks, not enough reads | Batch (see above) |
| Switching models mid-task | Each model has its own cache namespace | Commit to a model for a task chain |
| Large file reads varying across sessions | Variable content = variable cache key | Stable file snapshots or summaries as cache anchors |
| Compacting too aggressively | Post-compact context = new cache key | Compact at 65% pressure max, not earlier |

## Monitoring

**Daily cache health check:**
```bash
sqlite3 -column ~/.claude/usage.db "
SELECT model,
       printf('%.0f%%', 100.0*sum(cache_read_tokens)/sum(total_tokens)) AS cache_read,
       printf('%.0f%%', 100.0*sum(cache_creation_tokens)/sum(total_tokens)) AS cache_write,
       count(*) AS sessions
FROM sessions
WHERE timestamp >= datetime('now','-1 day')
GROUP BY model;"
```

**Alert thresholds:**

| Metric | Target | Alert |
|---|---|---|
| Opus/Sonnet cache-read | ≥96% | <93% → investigate prompt changes |
| Haiku cache-read | ≥90% | <85% → consolidate sessions |
| Cache-creation share | <5% | >8% → new content flood or prompt churn |
| Fresh token share | <2% | >5% → something is bypassing cache |

## Compaction Policy (cache-preserving)

- Compact at **50–65% context pressure** (per CONTINUOUS_EXECUTION_SOP.md).
- Do **not** compact earlier just to reduce session size — early compaction resets the
  cache key, costing a full re-creation cycle on the next turn.
- `autoCompactWindow` in `settings.json` is set to 110,000 tokens — do not lower this
  without measuring the cache-creation impact in `usage.db`.

## Weekly Review Checklist

- [ ] Run `usage-sync.sh --days 7` and review `model_breakdown` view.
- [ ] Check Haiku cache-read: if <90%, identify which task types ran in short sessions.
- [ ] Check cache-creation share: if >5% for Opus/Sonnet, a prompt changed — find it.
- [ ] Cross-reference with `OPUS_AUTHORIZATION_GATE.md` targets: is Opus % of spend trending down?
