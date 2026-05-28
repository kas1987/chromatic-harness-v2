# Agent Handoff: Chromatic Harness V2 — Governance & Routing System
**Date:** 2026-05-28
**Session:** Chromatic Harness V2 Initial + Governance Fixes
**Branch:** `session/chromatic-harness-v2-initial`
**Prev Branch:** `session/mc-x1bi-governance-fixes` (.claude repo)

---

## What We Built

### Phase 1: Core Router (Complete)
- `09_DEPLOYMENT/config/routing/providers.yaml` — Canonical provider inventory
- `09_DEPLOYMENT/config/routing/complexity-patterns.yaml` — C1-C4 keyword definitions
- `09_DEPLOYMENT/config/routing/routing-table.yaml` — 4 contexts × 3 speed modes × 4 C-levels
- `09_DEPLOYMENT/config/routing/user-preferences.yaml` — Speed mode, budget caps, API keys
- `02_RUNTIME/router/context_detector.py` — Probes GPU, Ollama, internet, battery
- `02_RUNTIME/router/complexity_classifier.py` — Maps task description → C1-C4
- `02_RUNTIME/router/provider_selector.py` — Resolves routing table + overrides
- `tests/test_complexity_and_routing.py` — 16 pytest cases, all passing

### Phase 2: Runtime Integration (Complete)
- `02_RUNTIME/router/gate.py` — Drop-in Python replacement for `model-router.sh` PreToolUse hook
- `02_RUNTIME/router/adapters/ollama_remote.py` — Remote Ollama adapter (desktop LAN)
- `02_RUNTIME/router/router.py` — Integrated context-aware routing into existing ChromaticRouter
- `tests/run-all-e2e.py` — pytest-based E2E runner (replaces broken bats on Windows)

### Phase 3: Research & Expansion (Complete)
- `.agents/research/2026-05-28/AI_INFRASTRUCTURE_RESEARCH_COMPENDIUM.md` — 25KB covering:
  - vLLM (PagedAttention, continuous batching, multi-GPU)
  - Ollama (distributed inference PR, GPU grouping, Kubernetes)
  - OpenAI/GPT (5.x series, o-series reasoning, pricing)
  - Anthropic/Claude (Opus 4.8, Sonnet 4.6, 1M context, extended thinking)
  - Google/Gemini (2.5 Pro/Flash/Flash-Lite, 1M context, thinking models)
  - Moonshot/Kimi (K2 MoE 1T params, K2.6, coding benchmarks)
  - Inflection/Pi (skip — not competitive for coding/reasoning)
  - OpenRouter (400+ models, auto-router, $113M Series B)
  - Together AI (ATLAS, FlashAttention-4, serverless)
  - Featherless (4000+ models, flat-rate, limited context)
  - RunPod (pay-per-second GPU, vLLM quick deploy)
- `.agents/research/2026-05-28/CLI_CODING_AGENTS_QUICKREF.md` — Claude Code vs Codex usage
- `.agents/codex-team/desktop-prep.md` — RTX 4070 setup guide (from Codex subagent)

---

## Key Decisions & Philosophy

### Capability-First Routing
**Do NOT rigidly enforce "C2 = cheap model."** Route based on what the task needs.

| Anti-Pattern | Correct Routing |
|--------------|----------------|
| "C2 must be cheap" → Ollama | "Debug race condition" → qwen2.5-coder:14b (purpose-built) |
| "Always local first" | "500K token doc" → Gemini Flash (1M context) |
| "Claude for everything" | "High-volume classification" → Gemini Flash-Lite (cheapest) |

### Speed Mode = Cost Discipline, Not Capability Gate
| Mode | Behavior |
|------|----------|
| **speed** | Advisory only. Never block. User wants best tool for job. |
| **balance** | Block non-tier-4 pure LLM calls (cost discipline). |
| **low** | Block non-local providers (force offline/local). |

### Kimi K2.6 — The Coding Dark Horse
- **SWE-bench Verified: 65.8%** — beats Claude Sonnet 4, GPT-4.1
- **LiveCodeBench v6: 53.7%** — competitive with frontier models
- **Price:** $1.20/$4.50 per 1M (via Together AI or OpenRouter)
- **Context:** 256K tokens
- **Use for:** Coding tasks, agentic workflows, as cheaper alternative to Claude

### Claude Opus 4.8 — The Agentic King
- **SWE-bench: 72.5%** — best coding model available
- **Price:** $5/$25 per 1M (now accessible, was $15/$75)
- **Context:** 1M tokens
- **Use for:** Complex coding, long-horizon agents, novel problems

---

## Provider Inventory (Updated)

| Provider | Type | Key Models | Cost Tier | Notes |
|----------|------|-----------|-----------|-------|
| Ollama (local) | Local | llama3.2:3b, qwen2.5-coder:14b | T0 | Laptop CPU / Desktop GPU |
| Ollama (remote) | Local LAN | llama3.1:8b, qwen2.5-coder:14b, gemma2:9b/27b | T0 | Desktop 4070 over LAN |
| Gemini | Cloud | Flash, Flash-Lite, Pro | T2-T3 | 1M context king |
| OpenAI | Cloud | GPT-5.4, 5.4-mini, o3, o3-mini | T2-T3 | Reasoning specialists |
| Claude API | Cloud | Opus 4.8, Sonnet 4.6, Haiku 4.5 | T3-T4 | Agentic leader |
| **OpenRouter** | **Cloud** | **All of above + 400 more** | **Passthrough** | **One key, auto-routing** |
| **Together AI** | **Cloud** | **Kimi K2.6, Llama 3.3 70B, Qwen3 235B** | **T2** | **Fastest open-source inference** |
| **Moonshot** | **Cloud** | **Kimi K2.6, K2 turbo** | **T2** | **Native Kimi API** |
| RunPod | Cloud GPU | Any open model | Variable | Pay-per-second GPU |
| Native Claude | Native | This session | T0 | Already paid (subscription) |

---

## API Keys Required

Set these in your environment or `.env`:
```bash
GEMINI_API_KEY          # Google Gemini
OPENAI_API_KEY          # OpenAI GPT / Codex
CLAUDE_API_KEY          # Anthropic Claude API
OPENROUTER_API_KEY      # OpenRouter unified (400+ models)
TOGETHER_API_KEY        # Together AI serverless
MOONSHOT_API_KEY        # Moonshot / Kimi native
RUNPOD_API_KEY          # RunPod GPU rental
ELEVENLABS_API_KEY      # TTS / voice
```

---

## Files That Changed (This Session)

### chromatic-harness-v2 repo:
```
09_DEPLOYMENT/config/routing/providers.yaml          # +OpenRouter, Together, Moonshot
09_DEPLOYMENT/config/routing/complexity-patterns.yaml # C1-C4 definitions
09_DEPLOYMENT/config/routing/routing-table.yaml        # +Kimi, OpenRouter Claude
09_DEPLOYMENT/config/routing/user-preferences.yaml     # +API keys, budgets
09_DEPLOYMENT/config/routing/model-capabilities.yaml  # 20+ models with capabilities
02_RUNTIME/router/context_detector.py                 # Device/context probe
02_RUNTIME/router/complexity_classifier.py              # C-level classifier
02_RUNTIME/router/provider_selector.py                # Routing resolver
02_RUNTIME/router/gate.py                              # PreToolUse hook
02_RUNTIME/router/adapters/ollama_remote.py            # Desktop LAN adapter
02_RUNTIME/router/router.py                             # Runtime integration
tests/test_complexity_and_routing.py                    # 16 pytest cases
tests/run-all-e2e.py                                    # pytest E2E runner
GOVERNANCE_AND_ROUTING_ARCHITECTURE.md                  # Full architecture doc
```

### .claude repo:
```
config/routing/user-preferences.yaml                   # Local copy (speed: balance)
hooks/pre-push.sh                                       # pytest E2E gate
hooks/model-router.sh → model-router.sh.deprecated      # Old bash router retired
settings.json                                           # PreToolUse → gate.py
```

---

## Current State

| Check | Status |
|-------|--------|
| PreToolUse hook | ✅ Wired to Python gate.py |
| Speed mode | ✅ `speed` (advisory only, no blocking) |
| Pre-push E2E | ✅ 16/16 pytest tests pass |
| Git push | ✅ Both repos pushed to origin |
| Closed beads | mc-ipn4, mc-xjmq, mc-u93w, mc-v1pw |

---

## Next Steps for Next Agent

1. **Desktop prep** — Follow `.agents/codex-team/desktop-prep.md` on RTX 4070
2. **API keys** — Get OPENROUTER_API_KEY, TOGETHER_API_KEY, MOONSHOT_API_KEY
3. **Test Kimi** — Verify `moonshotai/kimi-k2-6` via OpenRouter or Together AI
4. **Claude Code** — `claude` is installed; try `claude "refactor auth to JWT"`
5. **Codex** — `codex` is installed; try `codex --full-auto "fix the bug"`
6. **vLLM evaluation** — Compare vLLM vs Ollama on desktop 4070 for throughput

---

## How to Pick Up This Work

```bash
# 1. Pull the branch
cd ~/chromatic-harness-v2
git pull origin session/chromatic-harness-v2-initial

# 2. Run tests
python -m pytest tests/test_complexity_and_routing.py -v

# 3. Test the gate manually
cd 02_RUNTIME
echo '{"tool_name":"Agent","tool_input":{"description":"scaffold a new module","prompt":"","subagent_type":"general-purpose","model":""}}' | python router/gate.py

# 4. Read the research
ls .agents/research/2026-05-28/
```

---

## Contact / Context

- **User:** kas41
- **Machines:** Laptop (Windows + WSL2/Git Bash, no GPU, Ollama CPU) + Desktop (RTX 4070 12GB, Ollama GPU)
- **Current context:** Plugged in, speed mode active, full internet
- **Routing preference:** Capability-first, not cost-first
- **Closed issues:** mc-ipn4 (timeout fix), mc-xjmq, mc-u93w, mc-v1pw (governance bugs)

---

*Handoff version: 2026-05-28-001*
*Source: Session with Claude (native) + Codex subagent (desktop prep)*
