# `.agents/` — Meta-Governance Tier (the Flywheel)

> **Status:** canonical · **Tier:** meta-governance (out-of-band) · **Owner:** agent flywheel
> (all agents append; governance roles curate) · **Tracked by:** `chromatic-harness-v2-8lri.4`
>
> Formal companion to [`REPO_LAYERS.md`](../REPO_LAYERS.md) §3 and the structure source-of-truth
> [`CHROMATIC_TREES.md`](../CHROMATIC_TREES.md). Operational *behavior* lives in the root
> [`AGENT_OPERATIONS.md`](../AGENT_OPERATIONS.md); this file defines *what `.agents/` is and the
> rules for writing to it*.

## What this is

`.agents/` is the harness **flywheel**: the accumulated decisions, learnings, patterns,
handoffs, reviews, and governance records (~3,400 files) that capture *how the harness is
operated and how it improves over time*.

It is the **meta-governance tier** — it sits **above** the numbered layers (`00_`–`12_`) and
governs their operation, rather than being one of them. It is therefore **out-of-band**: it
intentionally lives outside the numbered scheme.

## Decision: out-of-band, not `13_AGENTS_AND_FLYWHEEL/` (8lri.4)

The structure-reorg epic posed a choice: promote this tier into a numbered layer
(`13_AGENTS_AND_FLYWHEEL/`) or keep it out-of-band and document it. **We keep it out-of-band**
as the dot-prefixed `.agents/`, and band `13` stays *reserved* (see `REPO_LAYERS.md` §1).

Why:
- The numbered layers (`00_`–`12_`) describe the **product** — runtime, protocols, data,
  deployment. `.agents/` describes the **process that operates the product**; mixing the two
  flattens a meaningful distinction.
- A dot-prefixed directory signals *tool/agent-managed working state*, not a hand-authored
  deliverable — consistent with `.beads/`, `.claude/`, `.codegraph/`.
- It is append-heavy machine-written state; numbering it would imply a stability and ownership
  contract it does not have.

## Write-policy (the rules)

1. **Append, don't rewrite.** Agents add dated records; they do not rewrite flywheel history.
2. **Background analysis is read-only on the repo.** Any background learning/analysis system
   writes **proposals to staging (`candidates/`) only** — it never auto-promotes, auto-edits
   curated knowledge, or auto-implements code. Promotion to `learnings/` / `patterns/` is a
   curated step. (Mirrors the global mandate in `~/.claude/CLAUDE.md`.)
3. **Every reader must guard its parse.** Files here may be **partially written** at read time.
   Wrap every `json.loads()` / `JSON.parse()` over `.agents/*.json` and `*.jsonl` in
   try/except (try/catch) and degrade gracefully — never crash on a half-written record.
4. **No secrets.** This tier is committed; never write credentials or tokens here.

## The flywheel

```
   observe ─▶ candidates/      (staging: proposed learnings/patterns, *.gitkeep seeded)
                  │  curate (human/governance review — never automatic)
                  ▼
            learnings/ + patterns/   (promoted, durable knowledge)
                  │  surfaced at session start (SessionStart hook) + on recall
                  ▼
            applied in work ─▶ reviews/ + metrics/ ─▶ (back to observe)
```

## Subdirectory map

| Area | Dirs | Role |
|------|------|------|
| **Knowledge flywheel** | `candidates/` (staging), `learnings/`, `patterns/`, `reviews/`, `findings/`, `metrics/`, `harvest/`, `raw_capture/` | Propose → curate → promote → measure the durable knowledge base |
| **Sessions & ops state** | `handoffs/`, `plans/`, `rpi/`, `swarm/`, `context/`, `locks/`, `ao/` | Live session/lifecycle state (handoff packets, plan/RPI/swarm progress, locks) |
| **Decisions & governance** | `decisions/`, `council/`, `audit/`, `audits/`, `evolve/`, `chronicle/` | Decision records, multi-model council outputs, audits, drift-triage, event log |
| **Knowledge sources** | `research/`, `skills/`, `retro/` | Research compendia, skill records, retrospectives |
| **Pointer** | `AGENT_OPERATIONS.md` | Redirect to the root operations checklist |

> Housekeeping notes (not blocking): `audit/` and `audits/` overlap and could be consolidated;
> `decisions/` is currently empty (seed with the first ADR-style record when one is made).

## Ownership

All agents (Claude, Cursor, Codex, Pi) may append; governance roles curate promotions out of
`candidates/`. Human-accountable to the repo owner of record (TwistKS). This tier never
overrides a higher-ranked source in `00_SOURCE_OF_TRUTH/_AUTHORITY.yaml`.
