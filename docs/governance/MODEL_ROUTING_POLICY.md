# Model Routing Policy — Local vs Cloud (OMH-2)

> **Single decision surface** for *when local (Ollama/Llama) wins vs when cloud frontier
> (Claude / GPT / Gemini) wins.* It consolidates the scattered routing rules into one
> policy and documents that routing is **enforced**, not advisory.
>
> Does **not** duplicate existing docs — it points to them:
> - `docs/governance/MODEL_ROUTING_RULES.md` — Sonnet+Kimi role assignment
> - `docs/routing/API_ROUTING_POLICY.md` — provider priority ladder
> - `docs/routing/PROVIDER_MATRIX.md` — per-provider capability matrix
> - `~/.claude/governance/model-routing-for-subagents.md` + `multi-router-matrix.yaml` — global tiers
> - `~/.claude/config/provider-tiers.json` / `router-patterns.json` — the live tier config

## 1. The provider ladder (cheapest → most capable)

| Tier | Provider | Class | Use when |
|---:|----------|-------|----------|
| 0 | Ollama / Llama (local) | Local | C1/C2 mechanical work, privacy-sensitive data, cheap repeated workers, offline |
| 1 | Featherless | Cloud (cheap) | Tier-0 overflow / Ollama down; bounded long-context workers |
| 2 | OpenAI (GPT) | Cloud frontier | Strong general reasoning, tool-use breadth, second opinion |
| 3 | Gemini | Cloud frontier | Very-long-context digestion, multimodal, cross-check |
| 4 | Claude (native) | Cloud frontier | C3/C4 design, synthesis, governance/risk review, ambiguity resolution |

## 2. Local vs Cloud decision

**Prefer local (tier 0, Ollama/Llama) when ALL hold:**
- Complexity is **C1–C2** (mechanical: format, extract, scaffold, lint, summarize).
- No deep cross-file reasoning or ambiguity to resolve.
- Data is **privacy-class P2+** (keep sensitive content off cloud) — local wins on privacy alone.
- The task is a **repeated worker** step where cost dominates and quality bar is "good enough".

**Prefer cloud frontier (tiers 2–4) when ANY holds:**
- Complexity is **C3–C4** (design, synthesis, multi-constraint trade-offs, security review).
- The task has **unclear scope / ambiguity** → route to Claude (tier 4) or human; never Llama.
- **High/critical risk** mutation → Sonnet plans, worker implements, Sonnet audits (high-risk pattern).
- Context exceeds local model's reliable window → Gemini (tier 3) or Kimi long-context worker.

**Tie-breakers:** privacy beats cost; cost beats marginal quality on C1/C2; for C3/C4 quality beats cost.

## 3. Enforcement (this is LIVE, not advisory)

Routing is enforced by the **PreToolUse hook `.beads/hooks/model-router.sh`** on every `Agent`
tool call:
- It scores the call into tiers 0–4 (`router-patterns.json`) and resolves provider/model (`provider-tiers.json`).
- When `ROUTER_BLOCK_ENABLED=true` (**default**), a pure-LLM `general-purpose` Agent call that
  scores **below tier 4** and has no tool-use is **denied** (`permissionDecision: deny`) and
  redirected to the cheaper tier. This is the enforcement: you cannot burn a frontier model on
  cheap pure-LLM work without an explicit model choice.
- **Escape hatches** (intentional): an explicit `model: haiku|sonnet|opus` is honored (caller decided);
  tool-using agents are never blocked; an active-skill tier floor prevents under-routing below the
  invoking skill's declared tier.
- **Resilience:** if Ollama is down (`ollama-status.json`), tier-0 is bumped to tier-1, with a
  cost-risk warning after `TIER0_BUMP_CAP` bumps.

To disable enforcement for a session (advisory-only), set `ROUTER_BLOCK_ENABLED=false` — but the
default and governed posture is **enforced**.

## 4. Verification
- Every routed call appends to `~/.claude/.agents/router/log.jsonl` (tier, provider, model, reason).
- Audit token cost vs tier with `~/.claude/bin/agent_token_audit.py`.
- Decision matrix source of truth: `~/.claude/governance/multi-router-matrix.yaml`.

## 5. Quick rule
**C1/C2 or private → local (Llama).  C3/C4, ambiguous, or high-risk → cloud frontier (Claude/GPT/Gemini).**
Enforcement is on by default; overriding requires an explicit model choice or `ROUTER_BLOCK_ENABLED=false`.
