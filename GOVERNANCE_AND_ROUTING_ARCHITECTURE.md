# Chromatic Harness V2 — Provider Inventory & Routing Architecture

> **Runtime context:** Laptop (Windows, constrained resources, intermittent connectivity)
> **Secondary context:** Desktop (RTX 4070, 12GB VRAM, high local throughput)
> **Last updated:** 2026-05-28
> **Status:** Draft — awaiting validation before implementation

---

## 1. Environment Detection

The router MUST detect runtime context before making routing decisions:

```python
class RuntimeContext:
    device_type: "laptop" | "desktop" | "server" | "cloud_vm"
    gpu_model: str | None           # e.g. "RTX 4070", None if no GPU
    gpu_vram_gb: float | None       # e.g. 12.0, None if no GPU
    ollama_reachable: bool
    ollama_models: list[str]        # ["llama3.2:3b", "qwen2.5-coder:14b"]
    remote_ollama: list[str]        # extra endpoints on LAN e.g. ["desktop.local:11434"]
    power_source: "battery" | "ac" | "unknown"
    connectivity: "full" | "limited" | "offline"
    memory_pressure: "low" | "medium" | "high"
```

**Current contexts:**

| Context | Device | GPU | Ollama Models | Role |
|---------|--------|-----|---------------|------|
| **A — This session** | Laptop | ❌ None | llama3.2:3b, qwen3-vl:4b, qwen2.5-coder:14b (CPU) | Primary dev machine right now |
| **B — Desktop** | Desktop | ✅ RTX 4070 (12GB VRAM) | *To be configured* — can run 13B–30B quantized on GPU | Home workstation |

**VRAM math for Desktop (RTX 4070, 12GB):**

| Model Size | Q4 Quant VRAM | Fits 12GB? | Speed |
|------------|---------------|------------|-------|
| 7–8B | ~5GB | ✅ Yes | Fast (GPU) |
| 13B | ~8GB | ✅ Yes | Fast (GPU) |
| 30B | ~18GB | ❌ No | Needs CPU offload (slow) or Q3 quant (~14GB, borderline) |
| 70B | ~40GB | ❌ No | Not feasible on this card |

**Recommended desktop model set:**
- `llama3.1:8b` → C1–C2 general purpose (fast, fits easily)
- `qwen2.5-coder:14b` → C2–C3 coding (fits fine, excellent at code)
- `gemma2:27b` → C3 reasoning (borderline at 12GB; try Q3 or 9B first)
- `llama3.1:70b` → Not feasible on 12GB VRAM alone; skip or use RunPod

### 1.1 Remote Ollama Discovery

If the desktop is on the same LAN, the laptop should be able to reach it:

```yaml
remote_ollama_endpoints:
  - name: "desktop-4070"
    host: "desktop.local"    # or IP, e.g. 192.168.1.42
    port: 11434
    gpu: "RTX 4070"
    vram_gb: 12
    models: [llama3.1:8b, qwen2.5-coder:14b]
    latency_ms: ~2–10        # LAN ping
    reliability: "when_awake"  # desktop may sleep
```

**Remote Ollama routing rule:** If remote endpoint is reachable AND has a model loaded that fits the task AND latency < 50ms, prefer it over cloud API for C2–C3 tasks.

---

## 2. Provider Inventory

### 2.1 Local / Zero-Marginal-Cost Providers

These are ALWAYS preferred on any machine because they work offline and cost nothing. The **desktop** extends this set significantly.

| Provider | How to Reach | Models (Laptop) | Models (Desktop RTX 4070) | Best For | Notes |
|----------|-------------|-----------------|---------------------------|----------|-------|
| **Ollama (local)** | http://localhost:11434 | llama3.2:3b, qwen3-vl:4b, qwen2.5-coder:14b | llama3.1:8b, qwen2.5-coder:14b, gemma2:9b/27b | C1–C3 local tasks | CPU on laptop; GPU on desktop |
| **Ollama (remote)** | http://desktop.local:11434 | — | Same as above | C2–C3 when laptop insufficient | Discovered via LAN; desktop must be awake |
| **LM Studio (local)** | http://localhost:1234 | Depends on loaded model | Depends on loaded model | C1–C3 when model loaded | Desktop can load 13B–27B easily |
| **Native Claude** | N/A — this session | claude-sonnet-4-6 | — | C3–C4 via API; C1–C2 via hooks | "Free" per-call (subscription already paid) |

### 2.2 Cloud API Providers (Require Internet + API Key)

These cost money per token. On the **desktop**, use only when local models insufficient. On the **laptop**, use more liberally since local models are weaker.

| Provider | Key Status | Models | Input $/1M | Output $/1M | Best For |
|----------|-----------|--------|------------|-------------|----------|
| **OpenAI** | ✅ Key present | gpt-4o-mini, gpt-4o, o3-mini | varies | varies | C2–C3 general purpose |
| **Gemini** | ✅ Key present | gemini-2.5-flash, gemini-2.5-pro, gemini-ultra | varies | varies | C2–C4; 2M context |
| **RunPod** | ✅ Key present | Self-hosted (Llama 70B, Mixtral) | GPU rental | GPU rental | C3–C4 when desktop too small |
| **Claude API** | ✅ Key present | claude-sonnet, claude-opus, claude-haiku | $3.00 / $15.00 | $15.00 / $75.00 | C3–C4 complex reasoning |
| **Featherless** | ❌ No key | Hermes-3 8B, Mistral 7B | ~$0–$0.50/1M | ~$0–$0.50/1M | C1–C2 cheap — currently UNAVAILABLE |

### 2.3 Provider Availability Matrix (Laptop Context)

```yaml
availability:
  ollama_local:
    status: ✅ UP
    device: laptop
    models: [llama3.2:3b, qwen3-vl:4b, qwen2.5-coder:14b]
    latency: ~50–500ms (CPU)
    cost: $0
    requires: none

  ollama_remote_desktop:
    status: ⚠️ NOT_PROBED
    device: desktop
    host: "desktop.local:11434"
    models: [llama3.1:8b, qwen2.5-coder:14b]
    latency: ~2–10ms (LAN)
    cost: $0
    requires: desktop awake + same LAN

  lmstudio_local:
    status: ⚠️ INSTALLED_BUT_NO_MODEL_LOADED
    models: []
    latency: unknown
    cost: $0
    requires: lms.exe + manual model load

  native_claude:
    status: ✅ ACTIVE (this session)
    models: [claude-sonnet-4-6]
    latency: ~500ms–3s
    cost: subscription (no per-call marginal cost)
    requires: active Claude session

  openai:
    status: ✅ KEY_PRESENT
    latency: ~300ms–2s
    cost: per-token
    requires: internet + OPENAI_API_KEY

  gemini:
    status: ✅ KEY_PRESENT
    latency: ~200ms–1.5s
    cost: per-token
    requires: internet + GEMINI_API_KEY

  runpod:
    status: ✅ KEY_PRESENT
    latency: ~500ms–5s (cold start)
    cost: GPU rental
    requires: internet + RUNPOD_API_KEY

  featherless:
    status: ❌ NO_KEY
    latency: N/A
    cost: N/A
    requires: FEATHERLESS_API_KEY (not configured)
```

---

## 3. T-Levels Re‑defined (Cost + Availability)

T-levels describe **how expensive/risky** a provider is. On a laptop, prefer lower T numbers.

| T-Level | Name | Providers | When to Use |
|---------|------|-----------|-------------|
| **T0** | Local Free | Ollama, LM Studio | Always preferred on laptop. Works offline. No cost. |
| **T1** | Cheap API | Featherless (unavailable), OpenAI gpt-4o-mini | For tasks local models can't handle but cost must stay low. Currently maps to gpt-4o-mini since Featherless unavailable. |
| **T2** | Standard API | Gemini 2.5-flash, OpenAI gpt-4o | Good balance of capability and cost. Default for C2–C3 tasks on laptop when T0 insufficient. |
| **T3** | Premium API | Gemini 2.5-pro/Ultra, Claude sonnet | High capability. For C3–C4 reasoning, long context, coding. |
| **T4** | Ultra-Native | Claude opus, Claude native, RunPod large | Maximum capability. Novel problem solving, creative writing, multi-step agentic tasks. Native Claude is "free" if already in session. |

> **Laptop heuristic:** Try T0 first. If insufficient, jump to T2 (Gemini flash) rather than T1 since Featherless is unavailable. Reserve T3–T4 for genuinely complex tasks.

---

## 4. C-Levels (Complexity Classification)

C-levels describe **how hard the task is**, independent of cost. This is what the router should FIRST determine before selecting provider.

| C-Level | Name | Description | Example Tasks | Preferred Provider (Laptop) |
|---------|------|-------------|---------------|---------------------------|
| **C1** | Mechanical | Transform, format, convert, extract, summarize short text. Single-step. No reasoning. | JSON→table, frontmatter parse, CSV reformat, boilerplate generation, simple regex | **Ollama llama3.2:3b** (fast, <1s) |
| **C2** | Structured | Code review, small refactor, single-file changes, smoke tests, pattern matching. Bounded scope. | Scaffold module, review PR, fix lint error, write unit test, simple debug | **Ollama qwen2.5-coder:14b** (good at code) or **Gemini 2.5-flash** if context >8k |
| **C3** | Reasoning | Multi-file integration, architecture decisions, root-cause analysis, design trade-offs. Requires synthesis. | Debug 500 error across 3 files, design API contract, review architecture, plan refactor | **Gemini 2.5-pro** (long context, cheap reasoning) or **Claude sonnet** (if agentic) |
| **C4** | Creative / Novel | Brainstorming, novel problem solving, creative writing, complex multi-step reasoning, research synthesis. Unbounded. | Design a new DSL, write creative copy, novel algorithm design, strategic planning | **Claude opus** or **Gemini Ultra** or **Native Claude** (if already in session) |

### 4.1 Complexity Detection Patterns

```yaml
complexity_signals:
  C1:
    keywords: ["convert", "format", "extract", "table", "frontmatter", "json", "boilerplate", "scaffold directory layout", "summarize"]
    max_files: 1
    reasoning_depth: none

  C2:
    keywords: ["scaffold module", "code review", "PR review", "smoke test", "lint", "refactor", "single-file", "debug", "fix"]
    max_files: 3
    reasoning_depth: shallow

  C3:
    keywords: ["debug", "root cause", "architecture", "integration", "multi-file", "design", "review", "trace dependencies", "refactor across"]
    max_files: 10
    reasoning_depth: medium

  C4:
    keywords: ["brainstorm", "design tradeoffs", "novel", "creative", "strategy", "research", "synthesize", "invent", "plan"]
    max_files: unlimited
    reasoning_depth: deep
```

---

## 5. Routing Matrix: C-Level × Privacy × Budget × Machine → Provider

The router must detect which machine it's running on before routing:
- **Laptop** → CPU-only Ollama; prefer local for C1–C2, cloud for C3–C4
- **Desktop (RTX 4070)** → GPU Ollama; can keep C2–C3 local
- **Laptop + Desktop awake on LAN** → remote Ollama for C2–C3

### 5.1 Laptop-Optimized Routing

When on the laptop (no GPU, CPU-only Ollama):

```
C1:
  → Ollama local llama3.2:3b (T0)
  → Fallback: Ollama local qwen2.5-coder:14b (T0)

C2:
  → Ollama local qwen2.5-coder:14b (T0)
  → Fallback: Remote Ollama desktop if reachable (T0)
  → Fallback: Gemini 2.5-flash (T2)

C3:
  → Gemini 2.5-pro (T3)
  → Fallback: Native Claude (T4)

C4:
  → Gemini 2.5-pro / Claude sonnet (T3–T4)
  → Fallback: Claude opus if budget allows
```

### 5.2 Desktop-Optimized Routing (RTX 4070)

When on the desktop (12GB VRAM GPU), shift the boundary — many C2–C3 tasks can stay local:

```
C1:
  → Ollama local llama3.1:8b (T0, GPU-fast)
  → Fallback: qwen2.5-coder:14b (T0)

C2:
  → Ollama local llama3.1:8b / qwen2.5-coder:14b (T0, GPU-fast)
  → Fallback: Gemini 2.5-flash (T2)

C3:
  → Ollama local qwen2.5-coder:14b or gemma2:27b (T0)
  → Fallback: Gemini 2.5-pro (T3)

C4:
  → Gemini 2.5-pro / Claude sonnet (T3)
  → Fallback: Claude opus (T4)
```

### 5.3 Remote-Ollama Routing (Laptop → Desktop over LAN)

When on the laptop but desktop is awake on the same LAN:

```
C2 + remote desktop reachable:
  → Remote Ollama qwen2.5-coder:14b (T0, GPU)
  → Fallback: Local Ollama qwen2.5-coder:14b (T0, CPU, slower)
  → Fallback: Gemini 2.5-flash (T2)

C3 + remote desktop reachable:
  → Remote Ollama qwen2.5-coder:14b or gemma2:27b (T0)
  → Fallback: Gemini 2.5-pro (T3)
```

> **Key insight:** Gemini 2.5-pro/Ultra handles MANY tasks that previously went to Claude T4 — at a fraction of the cost. Claude should be reserved for truly agentic, creative, or novel reasoning tasks. On the desktop with GPU, try local first for C2–C3 before burning cloud credits.

---

## 6. Playbooks & Pre-Context

### 6.1 C1 — Mechanical Tasks Playbook

**Pre-context to prepend:**
```
You are a fast text-processing assistant. Respond concisely.
Output ONLY the transformed data. No explanations.
```

**Tools allowed:** None (pure text transformation)
**Expected latency:** <2 seconds
**Cost:** $0 (local)

### 6.2 C2 — Structured Code Tasks Playbook

**Pre-context to prepend:**
```
You are a senior software engineer reviewing code.
Focus on correctness, edge cases, and maintainability.
If scaffolding, follow existing conventions in the repo.
```

**Tools allowed:** file read, bash (read-only), grep
**Expected latency:** 5–15 seconds
**Cost:** $0–$0.01 (local or flash)

### 6.3 C3 — Reasoning Tasks Playbook

**Pre-context to prepend:**
```
You are a senior architect. Think step-by-step.
Identify trade-offs, risks, and alternatives.
When debugging: hypothesize → test → validate → report.
```

**Tools allowed:** file read/write, bash, grep, web search (if needed)
**Expected latency:** 15–60 seconds
**Cost:** $0.01–$0.10 (pro-level)

### 6.4 C4 — Creative / Novel Tasks Playbook

**Pre-context to prepend:**
```
You are a senior research engineer and creative problem solver.
Explore multiple approaches before committing.
Question assumptions. Seek novel angles.
If uncertain, state confidence level explicitly.
```

**Tools allowed:** Full tool suite, multi-step reasoning, web search
**Expected latency:** 30s–5min (multi-turn possible)
**Cost:** $0.10–$1.00 (opus-level)

---

## 7. SDK & Tool Alignment

| Tool | C1 | C2 | C3 | C4 | Notes |
|------|---|---|---|---|-------|
| `read` | ✓ | ✓ | ✓ | ✓ | Always safe |
| `write` | ✓ | ✓ | ✓ | ✓ | Needs scope gate |
| `bash` (read-only) | ✓ | ✓ | ✓ | ✓ | grep, ls, cat, head |
| `bash` (write) | ✗ | ✗ | ask | ✓ | rm -rf, git push blocked for C1–C3 |
| `web_search` | ✗ | ✗ | ✓ | ✓ | C1–C2 should be self-contained |
| `Agent` spawn | ✗ | ✗ | ✓ | ✓ | C1–C2 don't need sub-agents |
| `web_fetch` | ✗ | ✗ | ✓ | ✓ | For research tasks only |

---

## 10. Speed Mode: Latency vs Cost Slider

On the laptop specifically, the user can select a **speed mode** that shifts the routing boundary independent of C-level:

| Mode | Meaning | C1→ | C2→ | C3→ | C4→ | Best For |
|------|---------|-----|-----|-----|-----|----------|
| **speed** | Fastest response, cost secondary | Ollama local (if <2s) else Gemini flash | Gemini flash | Gemini pro | Claude sonnet / Gemini ultra | Live coding, tight feedback loops, demos |
| **balance** | Default — cost-aware but not penny-pinching | Ollama local | Ollama local / remote | Gemini pro | Claude sonnet / Gemini pro | Daily development |
| **low** | Minimize external calls, maximize local | Ollama local | Ollama local / remote | Ollama local (try first) | Gemini pro (last resort) | Offline work, saving credits, plane wifi |

### Speed Mode Implementation

```python
class SpeedMode(Enum):
    SPEED = "speed"      # latency-first; cloud liberally
    BALANCE = "balance"  # cost-latency tradeoff; default
    LOW = "low"          # cost-first; local stubbornly
```

The **provider_selector** receives `speed_mode` as an input and shifts the routing table boundary accordingly. Speed mode is orthogonal to C-level: the same C3 task can go to Gemini (speed), Ollama (low), or either (balance).

### Speed Mode Detection (Auto)

If user doesn't specify, the router can infer from signals:
- Recent API call latency > 5s → auto-downshift toward `speed`
- No internet connectivity → force `low`
- Budget threshold exceeded → auto-downshift toward `low`
- Agent spawn from CLI with `--fast` flag → `speed`
- Agent spawn from VS Code extension → `balance` (default)
- Agent spawn during `git push` pre-push hook → `low` (don't burn cloud credits on gate checks)

### Speed Mode Persistent Preference

Stored in `~/.claude/config/routing/user-preferences.yaml`:

```yaml
speed_mode: balance   # user override; one of speed | balance | low
auto_adjust: true     # allow router to shift based on budget/connectivity
```

---

## 11. Implementation Plan — Priority Order

### Phase 1: Core Router (this session)
1. `09_DEPLOYMENT/config/routing/providers.yaml`
2. `09_DEPLOYMENT/config/routing/complexity-patterns.yaml`
3. `09_DEPLOYMENT/config/routing/routing-table.yaml`
4. `09_DEPLOYMENT/config/routing/user-preferences.yaml`
5. `02_RUNTIME/router/context_detector.py`
6. `02_RUNTIME/router/complexity_classifier.py`
7. `02_RUNTIME/router/provider_selector.py`

### Phase 2: Adapters (next session)
8. `02_RUNTIME/router/adapters/ollama_remote.py`
9. Wire router into `02_RUNTIME/router/router.py`
10. Replace `.claude/hooks/model-router.sh` with Python invocation

### Phase 3: Validation (next session)
11. pytest suite for complexity_classifier (50 test descriptions)
12. pytest suite for provider_selector (all C×speed×context combos)
13. Pre-push hook updated to run pytest instead of bats

---

## 12. Implementation Notes

### 12.1 What to Build

1. **`02_RUNTIME/router/context_detector.py`**
   - Detects laptop vs desktop vs server
   - Probes GPU (nvidia-smi, wmic)
   - Probes Ollama (localhost + configured remote endpoints)
   - Checks internet connectivity
   - Returns `RuntimeContext` dataclass

2. **`02_RUNTIME/router/complexity_classifier.py`**
   - Maps task description → C-level (C1–C4)
   - Uses keyword + scope + reasoning-depth heuristics

3. **`02_RUNTIME/router/provider_selector.py`**
   - Takes C-level + privacy + budget + **runtime context + remote Ollama list**
   - Returns ranked provider list
   - On laptop: prefers remote Ollama if desktop reachable and awake

4. **`09_DEPLOYMENT/config/routing/providers.yaml`**
   - Canonical provider inventory (this doc's section 2)
   - Includes remote Ollama endpoint definitions

5. **`09_DEPLOYMENT/config/routing/complexity-patterns.yaml`**
   - Canonical C-level definitions (this doc's section 4)

6. **`09_DEPLOYMENT/config/routing/routing-table.yaml`**
   - Canonical routing matrix (this doc's section 5)
   - Separate tables for: laptop offline, laptop online, desktop, remote-ollama

7. **`02_RUNTIME/router/adapters/ollama_remote.py`**
   - Adapter for reaching Ollama on desktop over LAN
   - Same interface as local Ollama adapter

### 12.2 What to Deprecate

- `~/.claude/hooks/model-router.sh` → replaced by Python gate
- `~/.claude/config/provider-tiers.json` → replaced by YAML configs above
- `~/.claude/config/router-patterns.json` → replaced by complexity-patterns.yaml
- `~/.claude/hooks/policy_gate.py` T4 deny list → replaced by C-level tool alignment + scope gate

---

## 13. Validation Checklist

Before this goes live:

- [ ] Ollama availability probe works (localhost:11434 /api/tags)
- [ ] **Remote Ollama probe works** (desktop.local:11434 /api/tags when awake)
- [ ] **Context detector correctly identifies laptop vs desktop** (GPU present → desktop)
- [ ] Complexity classifier correctly labels 50 known tasks
- [ ] Routing matrix routes C1 → Ollama (local or remote), C4 → Gemini/Claude consistently
- [ ] Pre-push hook runs pytest instead of bats (no process leaks)
- [ ] All old `model-router.sh` references removed from pre-push
- [ ] LM Studio detection works (if models loaded, route to T0)
- [ ] Budget gate caps weekly spend per provider
- [ ] Privacy gate blocks P5 from cloud providers (except native Claude)
- [ ] **Desktop model recommendations validated on RTX 4070** (llama3.1:8b, qwen2.5-coder:14b, gemma2:9b load and run)

---

## Appendix: Model Capability Quick Reference

| Model | Context | Coding | Reasoning | Creativity | Cost/1M (in/out) | Fits RTX 4070 12GB? |
|-------|---------|--------|-----------|------------|-------------------|---------------------|
| **llama3.2:3b** | 128K | ⭐⭐ | ⭐⭐ | ⭐⭐ | $0 | ✅ Yes (2GB) — laptop CPU OK |
| **llama3.1:8b** | 128K | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | $0 | ✅ Yes (~5GB) — **desktop GPU ideal** |
| **qwen2.5-coder:14b** | 128K | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | $0 | ✅ Yes (~9GB) — **desktop GPU, laptop CPU OK** |
| **qwen3-vl:4b** | 32K | ⭐⭐ | ⭐⭐ | ⭐ | $0 | ✅ Yes (3.3GB) — vision + text |
| **gemma2:9b** | 128K | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | $0 | ✅ Yes (~6GB) — **desktop GPU** |
| **gemma2:27b** | 128K | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | $0 | ⚠️ Borderline (~14GB Q4; try Q3) — desktop |
| gpt-4o-mini | 128K | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | $0.15 / $0.60 | N/A — cloud |
| gemini-2.5-flash | 1M | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ~$0.075 / $0.30 | N/A — cloud |
| gemini-2.5-pro | 1M | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ~$1.25 / $10.00 | N/A — cloud |
| gemini-ultra | 1M | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ~$5.00 / $15.00 | N/A — cloud |
| claude-sonnet-4-6 | 200K | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | $3.00 / $15.00 | N/A — cloud / native |
| claude-opus-4-6 | 200K | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $15.00 / $75.00 | N/A — cloud / native |
| claude-haiku-4-5 | 200K | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | $0.80 / $4.00 | N/A — cloud |
