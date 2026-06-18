# Opus Authorization Gate

> **Status:** Enforced
> **Cost basis:** Opus = $16.73/session avg; Sonnet = $2.43/session avg (7× ratio, 2026-06-16/17 actuals)
> **Default:** All agent work routes to Sonnet unless explicitly authorized below.

## The Rule

**Opus requires explicit written justification before dispatch.** No justification → route to Sonnet.

Opus ran at near-parity with Sonnet session counts (146 vs 125) in the first 2 days of tracking,
accounting for 89% of spend ($2,442 vs $304). The routing rules already specify Sonnet-first;
this gate enforces them at dispatch time.

## Allow-List: When Opus Is Justified

| Trigger | Criterion | Evidence Required |
|---|---|---|
| Novel architecture decision | No prior pattern in codebase; tradeoffs span ≥3 subsystems | Stated in mission packet |
| Cross-repo synthesis | >5 repos or >150k tokens of novel (non-cached) content | Token estimate in mission packet |
| Critical risk audit | `risk_level = critical` per CONFIDENCE_GATE.md | Confidence gate score attached |
| Final merge gate for production change | Affects live data path, auth, or external API contract | PR link + diff summary |
| Deliberate extended reasoning | Task explicitly benefits from chain-of-thought depth that Sonnet demonstrably fails | Prior Sonnet attempt result attached |

If the task does not meet **at least one** criterion above, it must route to Sonnet.

## Deny-List: Never Route to Opus

- Implementation drafts and refactors → Kimi / Featherless
- Repo scanning and search → Kimi or Haiku
- PDR writing (first draft) → Sonnet
- Routine code review → Sonnet
- Any leaf agent task → Haiku
- Workflow sub-agents → Sonnet (default) or Haiku (cheap workers)
- "Just to be safe" escalations → not valid justification

## Authorization Process

1. **Fill mission packet** (`AGENT_MISSION_PACKET_TEMPLATE.md`) with `model: opus` and `opus_justification:` field.
2. **State the criterion** from the allow-list above.
3. **Log to `07_LOGS_AND_AUDIT/AGENT_RUN_LOG.jsonl`** before dispatch with `model`, `justification`, and `estimated_cost_usd`.
4. **After session:** record actual cost in the log. If actual > $50, file a cost incident using `COST_INCIDENT_TEMPLATE.md`.

## Cost Budget by Opus Use

| Use frequency | Acceptable daily Opus spend |
|---|---|
| Routine (most days) | $0 — Sonnet handles it |
| Occasional (architecture phase) | <$100/day |
| Intensive (major refactor / audit) | <$300/day — requires human sign-off |
| Above $300/day | Incident trigger; halt until reviewed |

## Enforcement Integration

- `model-router.sh` (PreToolUse Agent hook): deny Opus agent spawns that lack `opus_justification` in their prompt.
- Daily `usage-sync.sh` output: if Opus session count ≥ Sonnet count, flag as routing discipline failure.
- Weekly `model_breakdown` view: Opus share of cost should trend toward <30% of total spend.

## Target State

| Metric | Current (2026-06-17) | Target |
|---|---|---|
| Opus sessions / day | 73 | <20 |
| Opus % of total spend | 89% | <30% |
| Avg Opus session cost | $16.73 | <$25 (fewer, intentional sessions) |
| Sonnet sessions / day | 63 | 80–100 |
| Haiku sessions / day | 6 | 30–50 |
