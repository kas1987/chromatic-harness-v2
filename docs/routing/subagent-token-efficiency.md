# Subagent Token-Efficiency Doctrine

**Status:** v1 · **Date:** 2026-05-30 · **Scope:** all Prism repos on C: + native
Claude Code, regardless of IDE/CLI · **Federate:** copy to repo governance dirs
alongside `multi-router-matrix.yaml`.

> Grounded in a real audit (`~/.claude/bin/agent_token_audit.py`) of two
> 7-agent workflows. Finding: **output was ~1% of tokens.** Cost is dominated by
> (a) ~150–200k **fresh boot input per agent** and (b) **cache-read sprawl**
> across high-turn agents (one agent: 44 turns → 1.89M cache reads). Therefore
> the levers are: **boot lighter, turn fewer, route cheaper** — NOT "generate
> less."

## The 5 enforceable rules

### R1 — Route per agent by C-level, never default everything to the session model
The orchestrator inherits Opus; subagents MUST NOT unless the task is C4.
Apply `multi-router-matrix.yaml` per `agent()` / Agent dispatch:

| Task C-level | `model` | Why |
|---|---|---|
| C1 mechanical (config edit, format, scaffold, fixture) | `haiku` (router tags local/OL) | ~10x cheaper; zero judgment |
| C2 structured (single-file, smoke test, 1-file review) | `haiku`/`sonnet` | cheap tier suffices |
| C3 reasoning (multi-file integration, root-cause) | `sonnet` | strong, mid cost |
| C4 creative (design, architecture, synthesis) | `opus` (or inherit) | reserve premium here |

> Audit example of the violation: bead B10 (a YAML edit, pure C1) ran on Opus.
> That work belonged on haiku/local.

### R2 — Pass REFERENCES, not payloads
Do NOT inline large JSON/context into every parallel agent's prompt — it
multiplies fresh input by the fan-out width. Instead pass **file paths** and a
1–3 line brief; let each agent read only the slice it needs.

> Audit example: the design workflow inlined the full `surveyBrief` JSON into all
> 3 design agents + the synthesis agent. Write it to a temp file once, pass the
> path. Saves ~Nx the payload size where N = fan-out.

### R3 — Minimize the tool surface per agent (`agentType`)
Read-only survey/search agents → `agentType: 'Explore'` (read-only, fewer tool
schemas loaded, reads excerpts not whole files). Reserve the full tool set for
agents that actually edit/run. Fewer tool schemas = smaller boot payload.

### R4 — codegraph-first; ban grep+read exploration loops
For "where/how/what-calls" questions, agents MUST use `codegraph_context` /
`codegraph_explore` / `codegraph_trace` (2–3 calls), NOT grep+Read sweeps
(dozens of calls). This is the single biggest cut to **cache-read sprawl** — the
high-turn agents in the audit were grep/read looping.

### R5 — Scope to one artifact; cap the turns
One agent = one file/deliverable with explicit done-criteria. Tight scope keeps
turn count low; turn count is what makes cache reads balloon (each turn re-reads
the whole transcript). Prefer more, smaller, well-scoped agents over few
open-ended ones — but only when truly independent (R-parallelism).

## Orchestrator checklist (apply before every fan-out)
- [ ] Each agent assigned a `model` by its C-level (R1) — Opus only for C4.
- [ ] Shared context written to one file; agents get the path, not the blob (R2).
- [ ] Read-only agents use `agentType: 'Explore'` (R3).
- [ ] Prompt instructs codegraph-first, no grep/read loops (R4).
- [ ] Each agent has a single artifact + done-criteria; no open-ended "investigate everything" (R5).
- [ ] Schema-constrained returns (`schema:`) so output stays terse and structured.

## Native Claude Code (no workflow) — same principles
- Use `Explore`/`Plan` agentTypes for read-only fan-out; reserve the
  general-purpose agent for work that mutates.
- Don't dispatch a subagent for what a direct codegraph/Grep/Read call answers —
  a subagent pays the ~150k boot tax; a direct tool call pays ~0.
- Keep `CLAUDE.md` lean: every token in it is re-billed on every subagent boot.
  Move rarely-needed doctrine to on-demand files (load when relevant), not the
  always-injected `CLAUDE.md`.

## Effort Level Rules (addendum to R1 — 2026-06-02)

Effort levels control the extended thinking budget and multiply output cost at the model's output rate.
Reference: `C:\.00_True_AI\model-effort-routing.md` (full matrix + CSV).

### E1 — Subagents run minimum viable effort, not session default
The orchestrator inherits the session effort. Subagents MUST be dispatched at the effort level
the task actually requires — defaulting to session-max effort across a fan-out multiplies cost by N×fan-out.

### E2 — Gate high/max effort before dispatch; thinking tokens multiply cost
Sonnet at max effort can cost 3–5× Sonnet at low. Verify the task is reasoning-bound (inference
chains, logic steps) before dispatching high/max. Knowledge-bound tasks (recall, synthesis, creativity)
do NOT improve from thinking — route to Opus low instead.

### E3 — Sonnet max > Opus low cost at the crossover — prefer Opus low
For C3–C4 analytical tasks where the crossover exists:
  Sonnet max: ~$0.30–0.80/call | Opus low: ~$0.10–0.25/call
Opus low is cheaper AND higher quality in the crossover zone. Prefer it unless Opus quota is exhausted.

| Effort | Haiku | Sonnet | Opus |
|--------|-------|--------|------|
| low | C1-C2, ~$0.001-0.01 | C2, ~$0.02-0.05 | C4, ~$0.10-0.25 |
| medium | N/A (no thinking) | C2-C3, ~$0.05-0.15 | C4, ~$0.20-0.60 |
| high | N/A | C3-C4, ~$0.15-0.40 | C4, ~$0.50-1.50 |
| max | N/A | C4, ~$0.30-0.80 | C4, ~$1.00-3.00 |

### E4 — Haiku effort is a no-op; never set high/max for Haiku subagents
Haiku 4.5 has no extended thinking. Dispatching it at high/max effort wastes overhead with zero gain.

### E5 — Opus max requires explicit justification at dispatch site
$1–3+/call. Reserve for irreversible decisions, security audits, correctness-critical one-shots.

## Measurement
`python ~/.claude/bin/agent_token_audit.py <workflow_transcript_dir>` — per-agent
fresh-input / cache-read / output breakdown. Run it after big workflows; if
avg fresh-input/agent > ~120k or any agent > 30 turns, a rule above was skipped.

## Targets (from the audit baseline)
- Read-only survey agent: < 80k fresh input (Explore + codegraph), was ~140–215k.
- Mechanical (C1/C2) agents: on haiku/local, not Opus — ~10x $ cut, quota-neutral.
- Per-agent turns: < 30 (codegraph-first); the 44-turn outlier is the anti-pattern.
- Output stays terse via `schema:` — already good (~1% of tokens).
