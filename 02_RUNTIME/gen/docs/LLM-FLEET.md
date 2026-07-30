# LLM Fleet Reference

> Canonical reference for all LLM providers, Ollama models, routing rules, and MiniMax setup.
> Updated: 2026-07-30

---

## Provider Matrix

| Provider | Type | Context | Cost | Routing Trigger | Status |
|----------|------|---------|------|-----------------|--------|
| **claude** | Cloud (Max plan) | 200K | $0 (subscription) | Default; code/dispatch tasks | Always available |
| **gpt** | Cloud (API key) | 128K | $0.00015/1k in | `budgetConstraint=low` + <10K tokens | Requires `OPENAI_API_KEY` |
| **gemini** | Cloud (API key) | 1M | $0.0001/1k in | `requiresVision=true` | Requires `GEMINI_API_KEY` |
| **minimax** | Cloud (229B MoE) | 198K | $0.0002/1k in | `estimatedInputTokens > 50_000` | See setup below |
| **ollama_cloud** | Cloud (Ollama frontier API) | 128K+ | Varies | `ollama_cloud` provider in harness config | Requires `OLLAMA_API_KEY` |
| **lm-studio** | Local (OpenAI-compat) | 128K | Free | Heavy local inference | Requires LM Studio running |
| **ollama** | Local (lightweight) | 32K | Free | `requiresLocal=true`; NSFW vision; final fallback | Requires Ollama running |

**Fallback chain:** `claude → gpt → gemini → minimax → lm-studio → ollama`

---

## MiniMax Setup

MiniMax-M2.5 is a **229B MoE model** (mixture-of-experts). It is **cloud-only** on this hardware:

| Mode | VRAM Required | Status |
|------|--------------|--------|
| Local GGUF (3-bit / UD-Q3_K_XL) | 101 GB RAM | Not viable (RTX 4070 = 12 GB) |
| Local GGUF (8-bit / Q8_0) | 243 GB RAM | Not viable |
| Cloud via Ollama `:cloud` tag | 0 GB (cloud) | **Recommended** |
| Direct MiniMax API | 0 GB (cloud) | Alternative |

### Option A: MiniMax via Ollama `:cloud` tag (Recommended)

Ollama's `:cloud` tag routes to MiniMax's infrastructure — the model runs on their servers, not locally. The `ollama pull` downloads only a small routing manifest (~few KB), not model weights. Check `ollama.com/library/minimax` for the current tag, then pull it:

```bash
# Pull the cloud routing manifest (tiny — not the 229B weights)
ollama pull minimax-m2.7:cloud

# Also available (verify current tags on ollama.com/library):
ollama pull minimax-m2.5:cloud   # previous generation
ollama pull minimax-m2.1:cloud   # stable
ollama pull minimax-m2:cloud     # base
```

Then enable in gen/:
```bash
# .env or environment
GEN_ENABLE_MINIMAX=true
GEN_MINIMAX_URL=http://127.0.0.1:11434/v1
GEN_MINIMAX_MODEL=minimax-m2.5:cloud
```

### Option B: Direct MiniMax API

```bash
GEN_ENABLE_MINIMAX=true
GEN_MINIMAX_URL=https://api.minimax.chat/v1
GEN_MINIMAX_API_KEY=
GEN_MINIMAX_MODEL=abab6.5-chat   # check platform.minimax.io for current model IDs
```

### Option C: Ollama Cloud Frontier API

The harness `ollama_cloud` provider calls Ollama's paid cloud API for frontier-class models (no local GPU required). This is **separate** from the MiniMax `:cloud` tag above.

Current default model: `qwen3:235b` (Qwen3 235B MoE, 128K context, strong coding/reasoning).

```bash
# Required env var
OLLAMA_API_KEY=

# In harness config (config/routing/providers.yaml)
#   ollama_cloud:
#     base_url: https://ollama.com
#     model: qwen3:235b
```

To use a different Ollama Cloud model, change `model` in `config/routing/providers.yaml` and verify it is available at `ollama.com/library`.

### Verify

```bash
curl http://localhost:43123/transparency/status | jq .snapshot.activeLlm
# Test routing: large-context task should suggest minimax
curl -X POST http://localhost:43123/hooks/user-prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "analyze this document: '"$(python3 -c "print('x'*51000)")"'", "sessionId": "test"}' \
  | jq .suggestedLlm
```

---

## Ollama Fleet (Installed Models)

Hardware: **RTX 4070, 12 GB VRAM** shared with ComfyUI (peaks at ~9 GB during generation).

### VRAM Tiers

| Tier | VRAM | Safe When | Models |
|------|------|-----------|--------|
| **light** | ≤5 GB | Always (even during ComfyUI generation) | qwen3:4b, qwen3-vl:4b, nsfw-tagger:latest |
| **medium** | 5–10 GB | ComfyUI idle | mistral:latest, qwen2.5-coder:7b, deepseek-r1:7b, qwen3:8b, qwen3-vl:8b, llava:7b |
| **heavy** | >10 GB | Idle only (time-sliced with ComfyUI) | phi4:latest, qwen2.5-coder:14b, qwen3:14b, gemma4:27b |
| **vision-nsfw** | 3.3 GB | Always (light tier) | huihui_ai/qwen3-vl-abliterated:4b-instruct |

### Recommended Model Per Session Mode

| Session Mode | ComfyUI State | Recommended Ollama Model | Rationale |
|-------------|---------------|--------------------------|-----------|
| `heavy` | Actively generating | `qwen3:4b` | Only light models safe; 2.5 GB leaves ~0.5 GB buffer |
| `light` | Idle | `mistral:latest` | 4.4 GB; good general-purpose reasoning |
| `idle` | Not running | `qwen2.5-coder:14b` | 9 GB; best coding quality available locally |

### Config Default

`GEN_OLLAMA_MODEL=qwen3:4b` (light tier default — safe in all modes)

To override for a session: `GEN_OLLAMA_MODEL=qwen2.5-coder:14b npm run dev`

### Vision-NSFW Tier

For NSFW image analysis (RAG, confidence scoring, tagger inference), standard `qwen3-vl` has content refusals on explicit material. The abliterated variant removes those restrictions.

```bash
# Install the abliterated vision model (3.3 GB — light tier)
ollama pull huihui_ai/qwen3-vl-abliterated:4b-instruct
```

**Routing:** When `requiresVision=true` AND `nsfwContext=true`, the selector routes to Ollama instead of Gemini, using this model. Set `nsfwContext: true` in the task payload to activate.

---

## Routing Logic

```
selectBestLlm(task):
  1. requiresLocal=true                   → ollama
  2. requiresVision + nsfwContext          → ollama (qwen3-vl-abliterated — no content refusals)
  3. requiresVision=true                  → gemini
  4. budgetConstraint=low                 → gpt (<10K tokens) or ollama (≥10K tokens)
  5. estimatedInputTokens>50K             → minimax  (198K window vs Ollama's 32K limit)
  6. requiresCode or code                 → claude
  7. performanceTracker hit               → learned model
  8. default                              → claude
```

**Availability fallback:** `selectAvailableLlm()` probes preferred provider first, then walks `FALLBACK_CHAIN` until one responds. Returns `"ollama"` unconditionally if all fail.

---

## Cross-Agent Transparency

All routing decisions are visible via the transparency endpoint:

```bash
GET http://localhost:43123/transparency/status
→ { snapshot: { activeLlm, routingConfidence, activeTasks, upcomingWork, driftAlerts } }

GET http://localhost:43123/transparency/drift
→ { alerts: [...], driftRate: 0.0 }
```

**Drift detection:** When `gen.actual_llm != gen.suggested_llm` in posttool hooks, the event is recorded with timestamp, suggested provider, actual provider, intent, and reason. `driftRate` is the fraction of the last 20 events that had divergence.

A high drift rate (>0.3) typically indicates:
- A preferred provider is consistently unavailable (check API keys / Ollama status)
- The routing rules don't match actual usage patterns (review `intentToRoutingHints`)
- Session cache TTL is too short (30s default in `LlmSelector._cachedAvailable`)
