---
name: ai-infrastructure-research-compendium
type: anti-pattern
confidence: 0.50
source_learnings: [AI_INFRASTRUCTURE_RESEARCH_COMPENDIUM]
description: Comprehensive AI Infrastructure Research Compendium
tags: []
---

# Comprehensive AI Infrastructure Research Compendium
## Date: 2026-05-28
## Purpose: Single source of truth for model routing, provider selection, and infrastructure decisions

---

## Table of Contents

1. [Inference Engines](#1-inference-engines)
   - [vLLM](#11-vllm)
   - [Ollama](#12-ollama)
2. [Cloud API Providers](#2-cloud-api-providers)
   - [OpenAI / GPT](#21-openai--gpt)
   - [Anthropic / Claude](#22-anthropic--claude)
   - [Google / Gemini](#23-google--gemini)
   - [Moonshot / Kimi](#24-moonshot--kimi)
   - [Inflection / Pi](#25-inflection--pi)
3. [Serverless / Routing Layers](#3-serverless--routing-layers)
   - [OpenRouter](#31-openrouter)
   - [Together AI](#32-together-ai)
   - [Featherless](#33-featherless)
   - [RunPod](#34-runpod)
4. [Model Routing Philosophy](#4-model-routing-philosophy)
5. [Capability Matrix](#5-capability-matrix)
6. [Cost Comparison](#6-cost-comparison)
7. [Update Protocol](#7-update-protocol)

---

## 1. Inference Engines

### 1.1 vLLM

**What it is:** The dominant open-source LLM inference engine. Originally from UC Berkeley Sky Computing Lab, now Linux Foundation incubation project.

**Key Technology:**
- **PagedAttention** — OS-style memory management for KV cache. Divides KV cache into fixed-size blocks (typically 16 tokens), allocated lazily per request. Eliminates over-allocation and external fragmentation.
- **Continuous Batching** — New requests join mid-batch; completed requests release slots immediately. GPU stays ~fully utilized.
- **Speculative Decoding** — Draft small model predicts multiple tokens; main model validates in parallel.
- **Chunked Prefill** — Splits long prompts into chunks to improve interleaving with decode steps.
- **Prefix Caching** — Shared system prompts reuse KV cache blocks across requests.

**Throughput Claims:**
- 14-24x higher throughput than HuggingFace Transformers
- 2.2-3.5x higher than HuggingFace TGI
- 2-24x more requests/sec than naive reference implementations

**Key Metrics:**
| Metric | Meaning | Target |
|--------|---------|--------|
| TTFT | Time to First Token | < 100ms for interactive |
| TPOT | Time Per Output Token | < 50ms (20 tok/s) |
| ITL | Inter-Token Latency | Smooth streaming |
| Throughput | Total tok/s across all requests | Maximize |

**Hardware Support:**
- NVIDIA (primary), AMD, Intel, TPU, ARM, PowerPC
- Plugins: Intel Gaudi, IBM Spyre, Huawei Ascend

**Quantization Support:** GPTQ, AWQ, AutoRound, INT4, INT8, FP8, MXFP4, NVFP4

**Deployment:**
- Single GPU: `python -m vllm --model <model>`
- Multi-GPU: Tensor/parallel/pipeline/data/expert parallelism
- API server: OpenAI-compatible `/v1/chat/completions`
- Kubernetes: Native support with GPU scheduling

**Version:** v0.18.1 (March 2026). V1 engine is current; V0 deprecated.

**Use When:**
- Self-hosting open-weight models at scale
- Maximum throughput per GPU dollar
- Production serving with OpenAI-compatible API
- Multi-GPU or multi-node deployment

**Source:** [vllm.ai](https://vllm.ai), [GitHub vllm-project/vllm](https://github.com/vllm-project/vllm)

---

### 1.2 Ollama

**What it is:** Local model runner for macOS, Linux, Windows. Wraps llama.cpp with a simple CLI and REST API.

**Key Features:**
- Single-command model pull: `ollama pull llama3.1:8b`
- REST API at `localhost:11434` (OpenAI-compatible subset)
- Automatic GPU detection and offload
- Model quantization handled automatically (Q4_K_M default)
- Modelfile system for customizing prompts, parameters, system messages

**2025/2026 Developments:**
- **Distributed Inference (PR #10844):** RPC support for multi-device inference via llama.cpp RPC. `ollama rpc` command. Works over Thunderbolt 4 for best performance.
- **GPU Grouping (PR #10678, merged):** `OLLAMA_SCHED_SPREAD=2` minimizes GPU count per model. Huge VRAM and power savings on multi-GPU systems. On 7x RTX 3060: 450W -> 310W, 27fps -> 81fps for Qwen3:14b.
- **Kubernetes Helm charts:** Production StatefulSet deployment with PVC model caching
- **Multi-model scheduling:** `OLLAMA_MAX_LOADED_MODELS` controls resident model count
- **Parallel requests:** `OLLAMA_NUM_PARALLEL` sets concurrent slot count

**Critical Environment Variables:**
```bash
OLLAMA_HOST=0.0.0.0          # Bind to all interfaces (for LAN)
OLLAMA_PORT=11434             # Default port
OLLAMA_NUM_PARALLEL=4         # Concurrent requests per model
OLLAMA_MAX_LOADED_MODELS=3    # Resident models before eviction
OLLAMA_SCHED_SPREAD=2         # Minimize GPUs per model (new)
OLLAMA_KEEP_ALIVE=5m         # How long to keep model loaded after last use
```

**VRAM Math (Q4_K_M):**
| Model | Parameters | VRAM | Fits RTX 4070 12GB? |
|-------|-----------|------|---------------------|
| llama3.2:3b | 3B | ~2.0 GB | Yes (laptop CPU) |
| llama3.1:8b | 8B | ~5.0 GB | Yes (desktop GPU ideal) |
| qwen2.5-coder:14b | 14B | ~9.0 GB | Yes (desktop GPU, tight) |
| qwen3-vl:4b | 4B | ~3.3 GB | Yes (vision + text) |
| gemma2:9b | 9B | ~6.0 GB | Yes (desktop GPU) |
| gemma2:27b | 27B | ~14.0 GB | Borderline (Q3 may fit) |

**Use When:**
- Local development and testing
- Single-machine deployment (laptop or desktop)
- Quick model switching
- LAN sharing within a home/office (with `OLLAMA_HOST=0.0.0.0`)
- Not suitable for: high-throughput production serving (use vLLM instead)

**Source:** [ollama.com](https://ollama.com), [GitHub ollama/ollama](https://github.com/ollama/ollama)

---

## 2. Cloud API Providers

### 2.1 OpenAI / GPT

**Current Model Lineup (May 2026):**

| Model | Context | Input/1M | Output/1M | Best For |
|-------|---------|----------|-----------|----------|
| **gpt-5.5** | 272K | $5.00 | $30.00 | General-purpose, fast |
| **gpt-5.5-pro** | 272K | $30.00 | $180.00 | Maximum capability |
| **gpt-5.4** | 272K | $2.50 | $15.00 | Balanced |
| **gpt-5.4-mini** | 272K | $0.75 | $4.50 | Speed + cost |
| **gpt-5.4-nano** | 272K | $0.20 | $1.25 | Cheapest GPT |
| **gpt-4o** | 128K | $2.50 | $10.00 | Vision + text |
| **gpt-4o-mini** | 128K | $0.15 | $0.60 | Cost-sensitive |
| **o3** | 200K | $2.00 | $8.00 | Deep reasoning |
| **o3-mini** | 200K | $1.10 | $4.40 | Reasoning, cheap |
| **o4-mini** | 200K | $1.10 | $4.40 | Vision + reasoning |
| **o1** | 200K | $15.00 | $60.00 | Legacy reasoning |
| **o1-pro** | 200K | $150.00 | $600.00 | Extreme reasoning |

**Key Distinction: GPT vs o-series**
- **GPT models** (4o, 4.1, 5.x): General-purpose, instruction-following, fast. GPT-4.1 has 1M context.
- **o-series** (o3, o4-mini): Reasoning specialists. Step-by-step problem solving. `reasoning_effort` parameter (low/medium/high). Slower but deeper.

**Batch API:** 50% discount, async processing
**Cached Input:** Up to 50% discount for repeated prompts
**Rate Limits:** Tier 5 = 10K RPM, 30M TPM

**Use When:**
- GPT-5.4-mini: Daily tasks, high volume
- o3: Complex reasoning, math, coding debug
- gpt-4o: Multimodal (image input)
- o1-pro: Only when all else fails (very expensive)

**Source:** [OpenAI API Docs](https://developers.openai.com)

---

### 2.2 Anthropic / Claude

**Current Model Lineup (May 2026):**

| Model | Context | Input/1M | Output/1M | Extended Thinking | Best For |
|-------|---------|----------|-----------|-------------------|----------|
| **Claude Opus 4.8** | 1M | $5.00 | $25.00 | No (Adaptive) | Maximum capability, coding |
| **Claude Opus 4.7** | 1M | $5.00 | $25.00 | Yes | Deep reasoning |
| **Claude Opus 4.6** | 1M | $5.00 | $25.00 | Yes | Deep reasoning |
| **Claude Opus 4.5** | 1M | $5.00 | $25.00 | Yes | Deep reasoning |
| **Claude Sonnet 4.6** | 1M | $3.00 | $15.00 | Yes | Best speed/capability mix |
| **Claude Sonnet 4.5** | 1M | $3.00 | $15.00 | Yes | General-purpose |
| **Claude Haiku 4.5** | 200K | $1.00 | $5.00 | No | Fastest, cheapest |
| **Claude Haiku 3.5** | 200K | $0.80 | $4.00 | No | Legacy fast option |

**Key Features:**
- **Extended Thinking Mode:** Toggle between fast responses and deep reasoning. Now with tool use during thinking (beta).
- **Parallel Tool Use:** Multiple tools called simultaneously
- **Computer Use:** Can control desktop environment (screenshot + mouse/keyboard)
- **1M Context Window:** Full million tokens on Opus and Sonnet
- **Prompt Caching:** Cache writes (5min=$6.25/MTok, 1h=$10/MTok), cache hits=$0.50/MTok
- **Claude Code:** Native VS Code / JetBrains integration, GitHub Actions support

**Versioning:**
- Dateless IDs (e.g., `claude-opus-4-8`) are pinned snapshots, not evergreen
- Dated IDs (e.g., `claude-opus-4-8-20251201`) also pinned
- Aliases resolve to latest pinned snapshot

**Availability:** Claude API (first-party), AWS Bedrock, Google Vertex AI, Microsoft Foundry
**Regional Endpoints:** 10% premium over global for data residency guarantees

**Use When:**
- Opus 4.8: Complex coding, long-horizon agent tasks (can work for hours)
- Sonnet 4.6: Default for most tasks — best balance
- Haiku 4.5: High-volume, latency-sensitive simple tasks
- Extended thinking: When standard response isn't deep enough

**Source:** [Claude API Docs](https://platform.claude.com)

---

### 2.3 Google / Gemini

**Current Model Lineup (June 2025):**

| Model | Context | Input/1M | Output/1M | Thinking | Best For |
|-------|---------|----------|-----------|----------|----------|
| **Gemini 2.5 Pro** | 1M | ~$1.25 | ~$10.00 | Yes (default) | Complex reasoning, coding, agents |
| **Gemini 2.5 Flash** | 1M | $0.30 | $2.50 | Yes (default) | Fast, cheap, high volume |
| **Gemini 2.5 Flash-Lite** | 1M | Lower than Flash | Lower | Optional (off by default) | Lowest cost, classification |
| **Gemini 2.0 Flash** | 1M | $0.075 | $0.30 | No | Legacy fast option |
| **Gemini Ultra** | 1M | ~$5.00 | ~$15.00 | No | Maximum capability (older) |

**Key Features:**
- **1M Token Context:** All 2.5 models support 1M tokens (can process 3 hours of video)
- **Thinking Budget:** Controllable reasoning depth via API parameter
- **Multimodal:** Text, image, audio, video, PDF (up to 3,000 files, 50MB each)
- **Grounding:** Google Search integration for factual queries
- **Code Execution:** Built-in Python execution for math/reasoning
- **Batch:** 50% discount available

**Pricing Notes (June 2025 update):**
- Flash input raised from $0.15 to $0.30 (output lowered from $3.50 to $2.50)
- Removed thinking vs non-thinking price difference
- Flash-Lite is new lowest-cost option with thinking optional

**Model IDs:**
- `gemini-2.5-pro` — GA, stable
- `gemini-2.5-flash` — GA, stable
- `gemini-2.5-flash-lite` — Preview

**Use When:**
- 2.5 Flash: Default for most tasks — cheapest with 1M context
- 2.5 Pro: When Flash fails — stronger reasoning, coding
- Flash-Lite: Classification, summarization at massive scale
- Any Gemini: When you need 1M context (long docs, video, huge codebases)

**Source:** [Google AI Studio](https://aistudio.google.com), [Gemini Docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini)

---

### 2.4 Moonshot / Kimi

**What it is:** Chinese AI lab (Moonshot AI) producing frontier open-weight models. Kimi K2 is their flagship.

**Current Model Lineup:**

| Model | Architecture | Context | Params | Best For |
|-------|-------------|---------|--------|----------|
| **Kimi K2** | MoE (1T total, 32B active) | 128K | 1T | Coding, agentic tasks |
| **Kimi K2.6** | MoE | 256K | 1T | Latest, thinking enabled |
| **Kimi K2.5** | MoE | 256K | 1T | Reasoning, coding |
| **Kimi K2 Turbo** | MoE | 256K | 1T | Speed (60-100 tok/s) |
| **Kimi K2 Thinking** | MoE | 256K | 1T | Deep reasoning |
| **Kimi k1.5** | Dense | 128K | ? | Earlier reasoning model |

**Key Technical Details (Kimi K2):**
- **MuonClip Optimizer:** Novel QK-clip technique for stable training at 1T scale. Zero loss spikes on 15.5T tokens.
- **Agentic Data Synthesis:** Large-scale synthetic tool-use demonstrations
- **RLVR + Self-Critique:** Reinforcement learning with verifiable rewards and self-evaluation

**Benchmark Performance (K2 Instruct):**
- LiveCodeBench v6: 53.7% (beats DeepSeek-V3, Qwen3-235B)
- SWE-bench Verified: 65.8% single attempt (beats Claude Sonnet 4, GPT-4.1)
- SWE-bench Multilingual: 47.3%
- AIME 2025: 49.5%
- GPQA-Diamond: 75.1%
- Humanity's Last Exam: 4.7%

**API:** OpenAI-compatible. Base URL: `https://api.moonshot.ai/v1`
**Thinking:** Enabled by default on K2.6. `reasoning_content` field in responses.

**Availability:**
- Together AI: `moonshotai/Kimi-K2.6` ($1.20 in / $4.50 out per 1M)
- OpenRouter: Available
- Local: Weights on HuggingFace (Kimi-K2-Instruct)

**Use When:**
- Coding tasks (especially competitive with Claude Sonnet 4)
- Agentic workflows (tool use, multi-step)
- Long-context tasks (256K)
- Cost-effective alternative to Claude for coding

**Source:** [Kimi API Platform](https://platform.kimi.ai), [GitHub MoonshotAI/Kimi-K2](https://github.com/MoonshotAI/Kimi-K2)

---

### 2.5 Inflection / Pi

**What it is:** Inflection AI's conversational model. Originally focused on emotional intelligence and personal assistant use cases.

**Current Models:**

| Model | Context | Input/1M | Output/1M | Best For |
|-------|---------|----------|-----------|----------|
| **Pi 3.0** | 8K | $2.50 | $10.00 | Conversational, emotional intelligence |
| **Productivity 3.0** | 8K | $2.50 | $10.00 | Instruction following, JSON output |
| **Pi 3.1-Preview** | 8K | TBD | TBD | Agentic workflows, tool calling (beta) |

**Key Features:**
- Emotional intelligence and tone mirroring
- Backstory/personality built-in
- Safety-focused (rejects harmful queries)
- No tool calling (Pi 3.0)
- Tool calling added in 3.1-preview

**Limitations:**
- Small context (8K)
- No vision
- Expensive for capability ($2.50/$10.00)
- Limited provider availability (mostly via OpenRouter/Kilo)

**Use When:**
- Conversational interfaces requiring emotional intelligence
- NOT recommended for: coding, reasoning, long-context, cost-sensitive tasks

**Source:** [Inflection AI](https://developers.inflection.ai)

---

## 3. Serverless / Routing Layers

### 3.1 OpenRouter

**What it is:** Unified API for 400+ models across 60+ providers. Drop-in OpenAI SDK replacement.

**Key Features:**
- **One API Key:** Access to Claude, GPT, Gemini, Llama, DeepSeek, etc.
- **Auto Router:** `openrouter/auto` — AI-powered model selection based on prompt complexity (powered by NotDiamond)
- **Fallbacks:** Automatic provider fallback if one is down
- **Price Passthrough:** No markup on inference (credit purchase fee only)
- **BYOK:** Bring Your Own Key — use provider keys directly, first N requests free
- **Dynamic Variants:**
  - `:nitro` — Sort by throughput (speed)
  - `:floor` — Sort by price (cheapest)
  - `:exacto` — Sort by tool-calling reliability
  - `:extended` — Longer context
  - `:thinking` — Reasoning enabled

**Model Metadata API:**
```json
{
  "id": "anthropic/claude-sonnet-4.6",
  "context_length": 1000000,
  "pricing": {"prompt": "0.003", "completion": "0.015"},
  "architecture": {
    "input_modalities": ["text", "image"],
    "output_modalities": ["text"]
  },
  "supported_parameters": ["tools", "tool_choice", "max_tokens", "temperature"]
}
```

**Funding:** $113M Series B (May 2026) — led by CapitalG, with NVentures, ServiceNow, MongoDB, Snowflake, Databricks

**Use When:**
- Accessing many models without managing multiple API keys
- Want automatic fallback for reliability
- Want auto-routing based on prompt type
- NOT for: lowest possible cost (small markup on BYOK), strict data residency

**Source:** [OpenRouter](https://openrouter.ai)

---

### 3.2 Together AI

**What it is:** Serverless inference platform for open-source models. Research-driven optimizations.

**Key Features:**
- **ATLAS:** Runtime-learning accelerators (up to 4x faster inference)
- **FlashAttention-4:** Custom CUDA kernels for Blackwell GPUs
- **Adaptive Speculative Decoding:** Predict multiple tokens per step
- **Quantization Without Compromise:** FP8/FP4 with quality preservation
- **OpenAI-compatible API**
- **Batch API:** 50% discount
- **Cached Input:** Up to 83% discount (Kimi K2.6: $1.20 -> $0.20)

**Pricing (Selected Models):**
| Model | Input/1M | Output/1M | Context |
|-------|----------|-----------|---------|
| Llama 3.3 70B | $0.88 | $0.88 | 131K |
| Qwen3.5 9B | $0.10 | $0.15 | 262K |
| Gemma 4 31B | $0.39 | $0.97 | 262K |
| Kimi K2.6 | $1.20 | $4.50 | 262K |
| DeepSeek V4 Pro | $2.10 | $4.40 | 512K |
| MiniMax M2.7 | $0.30 | $1.20 | 202K |
| GPT-OSS 20B | $0.05 | $0.20 | 128K |

**Dedicated Endpoints:**
- H100 80GB: $3.99/hour
- H200 141GB: $5.49/hour
- B200 180GB: $9.95/hour

**Use When:**
- Running open-source models serverless
- Need fastest inference for open models
- Want batch processing discounts
- NOT for: proprietary models (Claude, GPT)

**Source:** [Together AI](https://www.together.ai)

---

### 3.3 Featherless

**What it is:** Serverless inference for 4,000+ HuggingFace models. Flat-rate subscription, unlimited tokens.

**Key Features:**
- **Largest Model Catalog:** 4,000+ text generation models
- **Flat-Rate Pricing:** Unlimited requests, concurrency-based plans
- **No Token Counting:** Pay for concurrent slots, not tokens
- **Automatic Model Loading:** Any public HF model with 100+ downloads
- **Private Models:** Business customers can connect HF accounts
- **Privacy:** No prompt/completion logging

**Plans:**
| Plan | Concurrency | Max Model Size |
|------|-------------|----------------|
| Feather Basic | 2 slots | 15B |
| Feather Premium | 4 slots | Unlimited (70B+) |
| Feather Scale | 8 slots/unit | 72B |

**Concurrency Math:**
- 7B-15B models = cost 1
- 24B-34B models = cost 2
- 70B+ models = cost 4
- Example: Premium (4 slots) = 1x 70B OR 2x 32B OR 4x 7B

**Limitations:**
- All models served at FP8 (quantized)
- Context lengths: 4K, 8K, or 16K (not full model context)
- Rate limiting by concurrency, not throughput
- No tool calling on most models

**Use When:**
- Exploring many open-source models
- Predictable monthly cost (unlimited tokens)
- NOT for: full context lengths, tool calling, maximum throughput

**Source:** [Featherless.ai](https://featherless.ai)

---

### 3.4 RunPod

**What it is:** Serverless GPU platform. Pay-per-second for GPU time. vLLM-optimized.

**Key Features:**
- **Pay-Per-Second:** Only pay when workers are running
- **FlashBoot:** Sub-200ms cold starts with pre-warmed pools
- **vLLM Quick Deploy:** One-click deployment of any HF model
- **SGLang Support:** Alternative to vLLM for structured generation
- **Multi-GPU Workers:** Up to 4x 80GB GPUs per worker (320GB total)
- **Network Volumes:** Persistent model storage across workers
- **31 Global Regions**

**GPU Pricing (per second):**
| GPU | VRAM | Flex | Active |
|-----|------|------|--------|
| RTX 4000 series | 16GB | $0.00016 | $0.00011 |
| RTX 4090 | 24GB | $0.00031 | $0.00021 |
| L40/L40S | 48GB | $0.00053 | $0.00037 |
| A100 | 80GB | $0.00076 | $0.00060 |
| H100 | 80GB | $0.00116 | $0.00093 |
| H200 | 141GB | $0.00155 | $0.00124 |
| B200 | 180GB | $0.00240 | $0.00190 |

**Worker Types:**
- **Flex:** Scale to zero when idle (cheapest for variable workloads)
- **Active:** Always running (discounts available, best for consistent traffic)

**Use When:**
- Need full GPU control without managing hardware
- Variable/bursty workloads (scale to zero saves money)
- Running custom inference containers
- NOT for: steady low-volume (per-second billing has overhead)

**Source:** [RunPod](https://www.runpod.io)

---

## 4. Model Routing Philosophy

### Capability-First Routing

**Core Principle:** Route based on what the model is best at, not just cost.

**Anti-Patterns:**
- "C2 must be cheap" — Wrong if the task needs a capability cheap models lack
- "Always use local first" — Wrong if the task needs 1M context or deep reasoning
- "Claude for everything" — Wrong if Gemini Flash is sufficient and 10x cheaper

**Correct Examples:**
- "Summarize 500K token log" → Gemini Flash (1M context) beats Claude (200K)
- "Debug complex race condition" → qwen2.5-coder:14b (purpose-built) may outperform generalist
- "Design novel caching strategy" → Claude Opus (creative reasoning) over Gemini Pro
- "High-volume classification" → Gemini Flash-Lite or GPT-4o-mini

### Context-Aware Routing

**Dimensions to consider:**
1. **Task complexity** (C1-C4) — What does the task need?
2. **Model capability** — What is each model best at?
3. **Runtime context** — Local available? Internet? GPU? Battery?
4. **Speed mode** — User's latency/cost preference
5. **Privacy class** — Can data leave the machine?
6. **Budget** — Weekly spend cap

### Dynamic Re-Routing

**Signals for runtime adjustment:**
- Model returns garbage → Bump to stronger model, log failure
- Task takes too long → Bump to faster model or speed mode
- API error/rate limit → Fallback to next provider
- Budget threshold exceeded → Downshift to cheaper tier

### Provider Fallback Chain

**Recommended default chain:**
1. Try preferred provider
2. If error/rate limit → Try secondary provider for same model class
3. If all fail → Fallback to native Claude (always available in this session)
4. Log all failures for later analysis

---

## 5. Capability Matrix

### By Task Type

| Task | Best Local | Best Cloud (Cheap) | Best Cloud (Premium) | Avoid |
|------|-----------|-------------------|---------------------|-------|
| JSON-to-table | llama3.2:3b | Gemini Flash | GPT-4o-mini | Claude Opus |
| Code review | qwen2.5-coder:14b | Gemini Flash | Claude Sonnet | GPT-4o |
| Scaffold module | qwen2.5-coder:14b | Gemini Flash | Claude Sonnet | o3 |
| Debug complex bug | qwen2.5-coder:14b | o3-mini | Claude Opus | Gemini Flash |
| Multi-file refactor | qwen2.5-coder:14b (GPU) | Gemini Pro | Claude Opus | llama3.2:3b |
| Root cause analysis | qwen2.5-coder:14b | o3 | Claude Opus | Gemini Flash |
| Architecture design | gemma2:27b (if fits) | Gemini Pro | Claude Opus | Any local < 14B |
| Brainstorming | — | Gemini Pro | Claude Opus | o3 (too slow) |
| Novel problem solving | — | o3 | Claude Opus | Gemini Flash |
| Creative writing | — | Gemini Pro | Claude Opus | o3 |
| Long doc analysis (500K+) | — | Gemini Flash/Pro | GPT-4.1 | Claude (200K limit) |
| Video analysis (1hr) | — | Gemini Pro | — | All others |
| Agentic workflow | — | Kimi K2.6 | Claude Sonnet 4.6 | o3 (no tool use) |
| Math/Science reasoning | — | o3-mini | o3 / Claude Opus | Gemini Flash |
| High-volume chat | llama3.1:8b (GPU) | Gemini Flash-Lite | GPT-5.4-nano | Claude Opus |
| Vision + reasoning | — | GPT-4o | Gemini Pro | o3 (no vision) |

### By Context Length Need

| Context Needed | Models |
|---------------|--------|
| 8K | Most local models, Inflection Pi |
| 32K | Llama 3.1, Qwen 2.5, Gemma 2 |
| 128K | GPT-4o, GPT-OSS, Claude Haiku, Qwen3 |
| 200K | Claude Sonnet, o3, o3-mini |
| 256K | Kimi K2, Kimi K2.6 |
| 512K | DeepSeek V4 Pro |
| 1M | Gemini 2.5 (all variants), Claude Opus 4.8, GPT-4.1 |

---

## 6. Cost Comparison

### Per 1M Tokens (Output-focused pricing)

| Provider | Cheapest | Mid-Range | Premium |
|----------|----------|-----------|---------|
| **Local (Ollama)** | $0 | $0 | $0 |
| **Gemini** | Flash-Lite (~$0.15) | Flash ($2.50) | Pro ($10.00) |
| **OpenAI** | GPT-5.4-nano ($1.25) | GPT-5.4-mini ($4.50) | GPT-5.5 ($30.00) |
| **Claude** | Haiku 4.5 ($5.00) | Sonnet 4.6 ($15.00) | Opus 4.8 ($25.00) |
| **Kimi** | — | K2.6 via Together ($4.50) | K2.6 direct |
| **Together** | GPT-OSS 20B ($0.20) | Llama 3.3 70B ($0.88) | DeepSeek V4 Pro ($4.40) |
| **RunPod** | ~$0.11/hr (RTX 4000) | ~$0.37/hr (L40S) | ~$0.93/hr (H100) |
| **Featherless** | $0 (Basic plan, 2 slots) | $0 (Premium, 4 slots) | $0 (Scale, 8 slots) |

### Cost per 1K Requests (typical agent step: 12K input, 600 output)

| Model | Cost per 1K steps |
|-------|------------------|
| Gemini 2.5 Flash | ~$3.60 |
| GPT-4o-mini | ~$2.25 |
| Claude Haiku 4.5 | ~$15.00 |
| Claude Sonnet 4.6 | ~$45.00 |
| Claude Opus 4.8 | ~$75.00 |
| o3-mini | ~$15.84 |
| Local (Ollama) | $0 |

---

## 7. Update Protocol

**When to update this document:**
- New model released (check OpenRouter models API weekly)
- Pricing changes (check provider docs monthly)
- Personal observation: "gemma2:9b was surprisingly good at X"
- Community benchmark: New leaderboard results

**Update format:**
```markdown
### 2026-06-15 — Gemini 2.5 Pro price drop
- Pro input dropped from $1.25 to $0.75
- Source: https://ai.google.dev/pricing
- Verified: Yes (personal API usage)
```

**Sources to monitor:**
1. [OpenRouter Models RSS](https://openrouter.ai/models/rss)
2. [Together AI Blog](https://www.together.ai/blog)
3. [vLLM Blog](https://blog.vllm.ai)
4. [Anthropic Changelog](https://docs.anthropic.com/en/release-notes)
5. [OpenAI API Docs](https://platform.openai.com/docs)
6. [Google AI Blog](https://blog.google/technology/ai/)
7. [Moonshot AI GitHub](https://github.com/MoonshotAI)

---

## Appendix: API Endpoints

| Provider | Base URL | Authentication |
|----------|----------|----------------|
| OpenAI | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| Anthropic | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` / `CLAUDE_API_KEY` |
| Gemini | `https://generativelanguage.googleapis.com` | `GEMINI_API_KEY` |
| Kimi | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` |
| Together | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` |
| OpenRouter | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| RunPod | Endpoint-specific | `RUNPOD_API_KEY` |
| Featherless | `https://api.featherless.ai` | `FEATHERLESS_API_KEY` |
| Inflection | `https://api.inflection.ai` | `INFLECTION_API_KEY` |
| Ollama | `http://localhost:11434` | None |

---

*Document version: 2026-05-28-001*
*Next review: 2026-06-28*

