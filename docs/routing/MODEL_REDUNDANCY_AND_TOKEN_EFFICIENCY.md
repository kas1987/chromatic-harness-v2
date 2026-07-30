# Model Redundancy + Token Efficiency

> Canonical guide for choosing, falling back, and budgeting models in Chromatic Harness v2.
> See also: [API_ROUTING_POLICY.md](API_ROUTING_POLICY.md), [OPENROUTER_BROKER_POLICY.md](../governance/OPENROUTER_BROKER_POLICY.md), [CONFIDENCE_GATE.md](../governance/CONFIDENCE_GATE.md).

---

## Provider priority ladder (default)

| Rank | Provider class | Use when | Avoid when |
|---:|---|---|---|
| 1 | **Local Ollama / LM Studio** | Private, cheap, repetitive, classification, simple drafting, offline | High reasoning or very long context |
| 2 | **Broker: Featherless / OpenRouter** | Model experimentation, cheap cloud fallback, diversity | Sensitive data or strict compliance |
| 3 | **Frontier: Agnes / Gemini / OpenAI / Anthropic / Kimi** | High reasoning, code review, long synthesis, tool orchestration | Low-value batch work |
| 4 | **OpenHuman sidecar** | Personal memory, integration context, background user context | Primary routing, destructive actions |

**Rule:** no code path calls an external LLM API directly. All calls go through `ChromaticRouter.route()`.

---

## Default routing knobs

| Knob | Default | Where |
|---|---|---|
| Speed mode | `balance` | `config/routing/user-preferences.yaml` |
| User provider preference | `agnes` | `config/routing/user-preferences.yaml` |
| Agnes C2+ promotion | enabled | `provider_selector._apply_agnes_default()` |
| Privacy ceiling | P2 for most cloud | `config/routing/privacy-policy.yaml` |
| OpenRouter allowlist | enforced | `config/routing/openrouter-models.yaml` |
| Lean boot | enabled | `CHROMATIC_LEAN_BOOT=1` in `.claude/settings.json` |

### Speed modes

- **`low`** — local-only / offline. Battery or no internet overrides user preference.
- **`balance`** — local-first when reachable; cloud only when needed.
- **`speed`** — latency-tolerant cloud-first route.

Connectivity and battery always win over the user's persisted preference.

---

## Redundancy rules

1. **Every context needs two reachable providers.** The router probes health before selecting. If the first choice is down, it walks the ranked list.
2. **Keep Ollama local running as the cheapest fallback.** It costs $0, keeps data local, and works offline.
3. **For online work, keep at least one frontier + one broker configured.** Example: Agnes + OpenRouter, or Gemini + OpenRouter.
4. **OpenRouter is a fallback, not a default.** Use it when direct keys are missing or model diversity is required. It is blocked for P4/P5.
5. **Native Claude** (this session) is treated as a subscription-paid frontier route; it is the default for C3/C4 review/governance when available.

### What the router does automatically

- Probes each candidate's `/health` or equivalent.
- Drops cloud providers when `internet_reachable` is false.
- Drops OpenRouter and cloud for P4/P5 tasks.
- Promotes Agnes to first choice for online C2/C3/C4 if no local route is reachable (unless `agnes_default: false`).
- Applies the user's `provider_preference` and `provider_blocklist`.

---

## Token-efficiency rules

1. **Use local models for volume work.** C1 classification, formatting, simple conversion, and high-volume scaffolding should run on Ollama/LM Studio when available.
2. **Match model to task capability, not just price.**
   - Long-context summarization: Gemini Flash (1M context) beats Claude Sonnet on window size.
   - Coding/debugging: Qwen2.5-coder:14b (local) or Kimi K2 (cloud).
   - Architecture/synthesis/governance: Claude Sonnet/Opus or Agnes.
   - Creative reasoning: Claude Sonnet.
3. **Cache context aggressively.** Re-read the same file only when it changed. Avoid giant concatenated prompts.
4. **Use subagents/workflows for parallel work.** One big context window is usually more expensive and slower than multiple focused calls.
5. **Enable lean boot.** `CHROMATIC_LEAN_BOOT=1` skips the redundant token-governance loop when the last run is fresh (<6h).
6. **Audit MCP context.** Heavy MCP servers inflate every turn. Run `python scripts/audit_mcp_context.py --profile harness_dev` and disable unused servers (e.g., Resend, Playwright) for daily work.
7. **Respect weekly budget caps.** Caps are set per provider in `config/routing/user-preferences.yaml`. The router does not enforce them yet, so stop and escalate before a cap is breached.

### Provider cost cheat-sheet (per 1M tokens, approximate)

| Provider / model | Input | Output | Best for |
|---|---:|---:|---|
| Ollama local | $0.00 | $0.00 | Always-on local fallback |
| Agnes `agnes-2.5-flash` | $0.00 | $0.00 | C2–C4 online work when available |
| Gemini Flash | $0.075 | $0.30 | Long context, fast synthesis |
| Gemini Pro | $1.25 | $10.00 | Hard reasoning, multimodal |
| Kimi K2.6 | $1.20 | $4.50 | Coding, long context |
| OpenAI GPT-4o-mini | $0.15 | $0.60 | Cheap structured tasks |
| Anthropic Sonnet | $3.00 | $15.00 | Review, governance, creative reasoning |
| Anthropic Opus | $15.00 | $75.00 | Deep novel problems only |

---

## Decision matrix

| Task | Privacy | Connectivity | Budget | First try | Fallback |
|---|---|---|---|---|---|
| C1 classification | P0/P1 | any | low | `ollama_local:llama3.2:3b` | `gemini:gemini-2.5-flash` |
| C2 coding scaffold | P1/P2 | online | normal | `ollama_local:qwen2.5-coder:14b` | `agnes:agnes-2.5-flash`, `gemini:gemini-2.5-flash` |
| C3 debug / root cause | P1/P2 | online | normal | `native_claude` | `agnes:agnes-2.5-flash`, `gemini:gemini-2.5-pro` |
| C4 architecture | P1/P2 | online | high | `native_claude` / `claude_api:sonnet` | `openrouter:anthropic/claude-sonnet-4-6`, `gemini:gemini-2.5-pro` |
| Long-context summarization (>100K) | P1/P2 | online | normal | `gemini:gemini-2.5-flash` | `gemini:gemini-2.5-pro` |
| Sensitive / P4/P5 | P4/P5 | any | any | local only | another local provider |
| Offline | any | offline | any | local only | native_claude if available |

---

## Confidence gate integration

Before any mutation, produce a confidence block:

```json
{
  "confidence_score": 82,
  "risk_level": "low",
  "scope_clarity": 85,
  "evidence_quality": 80,
  "reversibility": "yes",
  "decision": "execute"
}
```

| Score | Decision |
|---:|---|
| 0–49 | halt / escalate |
| 50–69 | self-heal / plan only |
| 70–74 | plan only |
| 75–89 | execute reversible |
| 90–100 | execute |

- Commit: confidence ≥ 75
- Push: confidence ≥ 88 + tests green + risk not high/critical
- Merge: confidence ≥ 95 + low risk + CI green

---

## Keeping this guide current

After every significant session that changes routing behavior:

1. Update `09_DEPLOYMENT/config/routing/model-capabilities.yaml` with observed model performance.
2. Update `config/routing/routing-table.yaml` if the ranked provider order should change.
3. Update this doc if redundancy or efficiency rules change.
4. Commit with a message like `docs(router): refresh redundancy/efficiency defaults`.
