# OmniRoute Global Integration Plan

> **Bead:** `chromatic-harness-v2-wisp-2yz`  
> **Goal:** Make OmniRoute a first-class, globally available route in the Chromatic Harness v2 provider stack, so every agent, tool, IDE integration (including OpenCode), and script can use the local free-pooled LLM gateway through one OpenAI-compatible endpoint.

## What OmniRoute is (source: `diegosouzapw/OmniRoute`)

OmniRoute is an open-source Node.js gateway. It exposes a **local, OpenAI-compatible endpoint** at `http://localhost:20128/v1` and routes across 290 providers (~90+ free tiers, ~1.53B free tokens/mo). It is distributed as:

- `npm i -g omniroute`
- Docker: `diegosouzapw/omniroute`
- Source: `npm install && npm run dev`

Zero-config behavior:

```bash
curl http://localhost:20128/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"Hello!"}]}'
```

Key capabilities relevant to CHV2:

| Capability | How it maps to CHV2 |
|---|---|
| `auto` / `auto/coding` / `auto/fast` / `auto/cheap` | Let OmniRoute choose a free/cheap model — equivalent to a smart broker. |
| Provider prefixes (`cc/...`, `oc/...`, `felo/...`, `openai/...`, `anthropic/...`) | Direct model IDs that CHV2 can surface as aliases. |
| `/v1/models`, `/v1/chat/completions`, `/v1/embeddings` | OpenAI-compatible surface; reuse the existing OpenAI adapter pattern. |
| `REQUIRE_API_KEY=false` (default local) | No real secret; send dummy key `not-needed` or `not-needed`. |  # pragma: allowlist secret
| RTK + Caveman token compression | Saves 15–95% tokens; CHV2 can pass through or leave it to OmniRoute. |
| 4-tier fallback (subscription → API key → cheap → free) | Good resilience story, but CHV2 already has its own fallback chain. |

OpenCode config (confirmed in upstream docs):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "omniroute": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "OmniRoute",
      "options": {
        "baseURL": "http://localhost:20128/v1",
        "apiKey": "not-needed"  # pragma: allowlist secret
      },
      "models": {
        "auto": { "name": "Auto-Combo" },
        "auto-coding": { "id": "auto/coding", "name": "Auto Coding" },
        "deepseek-flash": { "id": "oc/deepseek-v4-flash-free", "name": "DeepSeek V4 Flash" }
      }
    }
  }
}
```

## Strategic fit in the CHV2 routing stack

Current preferred route order (from `docs/governance/OPENROUTER_BROKER_POLICY.md`):

```text
1. Local Ollama / LM Studio / native_claude
2. Remote Ollama over LAN
3. Direct provider API when configured
4. OpenRouter broker fallback
5. Premium/RunPod when justified
```

OmniRoute should be inserted as a **local free-tier gateway** between (3) and (4):

```text
1. Local Ollama / LM Studio / native_claude
2. Remote Ollama over LAN
3. Direct provider API (Anthropic, OpenAI, Google, Agnes)
4. OmniRoute local free gateway
5. OpenRouter broker fallback
6. Premium/RunPod when justified
```

Use it to:
- Run P0/P1 tasks for $0 when direct keys are present but paid quota is precious.
- Provide a no-key fallback for local experimentation.
- Reduce burn on high-volume, low-risk tasks (classification, small codegen, summarization).

Because OmniRoute still egresses to third-party free clouds, it is **not** appropriate for P4/P5 and only conditionally for P2/P3.

## Governance decisions to lock before implementation

| Decision | Proposed default | Notes |
|---|---|---|
| **Provider type** | `local_gateway` (or `broker` with `local: true`) | Runs on localhost, but routes outbound. |
| **Privacy ceiling** | `P1` default, `P2` opt-in | Same posture as OpenRouter. P4/P5 hard-block. |
| **API key** | dummy `not-needed` | `REQUIRE_API_KEY=false` is the local default. |  # pragma: allowlist secret
| **Cost tracking** | `$0.00` estimated/actual | Free-tier, but token usage still logged. |
| **Auto-start** | no | Harness probes health; user starts OmniRoute via npm/Docker. |
| **Token compression** | leave to OmniRoute | CHV2 does not reimplement RTK/Caveman; it can pass `X-OmniRoute-*` headers if later needed. |
| **Default model** | `auto` | Harness lets OmniRoute pick; alias list maps to specific IDs for reproducibility. |

## Implementation slices

### Slice 1 — Install / bootstrap the gateway

- Add `scripts/install_omniroute.py` that:
  - Detects OS and whether Node.js/npm are installed.
  - Runs `npm install -g omniroute` (or `pnpm`, `yarn` if configured).
  - Optionally runs `docker run -d --name omniroute --restart unless-stopped -p 20128:20128 diegosouzapw/omniroute` as an alternative.
  - Verifies the endpoint with `GET /v1/models` using dummy key `not-needed`.
- Add `docs/routing/OMNIROUTE_INSTALL.md` with:
  - One-command npm install.
  - Windows service / Task Scheduler hint for always-on.
  - Validation curl.

### Slice 2 — Adapter

Create `02_RUNTIME/router/adapters/omniroute_adapter.py`:
- Inherits from `BaseAdapter`.
- Base URL from config (`http://localhost:20128/v1`).
- Sends `Authorization: Bearer not-needed` (configurable via `env_key` defaulting to `OMNIROUTE_API_KEY` or a literal).  # pragma: allowlist secret
- `health()` probes `GET /v1/models`.
- `complete()` posts `/v1/chat/completions`.
- Supports the standard OpenAI response shape (`choices[0].message.content`, `usage.*_tokens`).
- Exposes `selected_model` in the returned `RouteResponse`.

Register it in `02_RUNTIME/router/adapters/adapters.yaml`:

```yaml
adapters:
  omniroute:
    module: "router.adapters.omniroute_adapter"
    class: "OmniRouteAdapter"
```

### Slice 3 — Provider registry entry

Add to `config/routing/providers.yaml`:

```yaml
omniroute:
  type: local_gateway
  enabled: true
  base_url: http://localhost:20128/v1
  env_key: OMNIROUTE_API_KEY  # pragma: allowlist secret
  model: auto
  privacy_max: P1
  cost_tier: free
  note: "Local OpenAI-compatible gateway to free pooled providers."
```

If `type` is constrained by the providers schema, extend the schema to allow `local_gateway` or add `local: true` to a `broker` type.

### Slice 4 — Model allowlist / mapping

Create `config/routing/omniroute-models.yaml`:

```yaml
version: "1.0"
models:
  - id: auto
    alias: auto
    allowed_complexity: [C1, C2, C3, C4]
    max_privacy: P1
    notes: "Zero-config auto-router."

  - id: auto/coding
    alias: auto-coding
    allowed_complexity: [C1, C2, C3]
    max_privacy: P1
    notes: "Coding-optimized auto-router."

  - id: auto/cheap
    alias: auto-cheap
    allowed_complexity: [C1, C2]
    max_privacy: P1
    notes: "Cost-optimized auto-router."

  - id: oc/deepseek-v4-flash-free
    alias: deepseek-flash
    allowed_complexity: [C1, C2]
    max_privacy: P1
    notes: "OpenCode Free DeepSeek V4 Flash."

  - id: felo/...
    alias: felo-default
    allowed_complexity: [C1, C2]
    max_privacy: P1
    notes: "Felo free tier placeholder; replace with exact model id from /v1/models."
```

The adapter should map the CHV2 alias to the OmniRoute model id. The provider selector should drop any OmniRoute model not in this allowlist.

### Slice 5 — Provider selector + routing table integration

Update `02_RUNTIME/router/provider_selector.py`:
- Add `omniroute` to `_ROUTING_TO_POLICY`.
- Treat it as a cloud/broker for privacy filtering (P4/P5 block; P3 human gate).
- Add an allowlist gate for OmniRoute models, analogous to OpenRouter.
- Ensure `omniroute` is ranked below direct frontier providers and above `openrouter` for P0/P1 tasks when reachable.

Update `config/routing/routing-table.yaml` to insert `omniroute` into the context matrices, e.g.:

```yaml
context_laptop:
  balance:
    C1: [ollama_local:llama3.2:3b, omniroute:auto]
    C2: [ollama_local:qwen2.5-coder:14b, omniroute:auto/coding, agnes:agnes-2.5-flash]
    C3: [native_claude, agnes:agnes-2.5-flash, gemini:gemini-2.5-pro, omniroute:auto/cheap]
    C4: [native_claude, agnes:agnes-2.5-flash, gemini:gemini-2.5-pro, claude_api:sonnet, omniroute:auto]
```

### Slice 6 — Governance policy

Create `docs/governance/OMNIROUTE_BROKER_POLICY.md` mirroring `OPENROUTER_BROKER_POLICY.md`:
- Role in the stack.
- Privacy classes (P0/P1 default; P2 opt-in; P3 human gate; P4/P5 block).
- Model allowlist source.
- Cost controls (free, but daily token budget to avoid rate-limit storms).
- Logging requirements.
- Failure handling (if OmniRoute unreachable, fall back to OpenRouter / direct providers).

### Slice 7 — OpenCode wiring guide

Create `docs/routing/OPENCODE_OMNIROUTE_SETUP.md`:
- Run OmniRoute on `localhost:20128`.
- Write `%USERPROFILE%\.config\opencode\opencode.json` (Windows) or `~/.config/opencode/opencode.json`.
- Provide the exact JSON snippet.
- Add a note on CHV2 privacy classes so users do not route secrets through free tiers.

### Slice 8 — Tests and smoke

- `tests/test_omniroute_adapter.py`: mock `httpx.AsyncClient` to verify request shape, health, and response normalization.
- `tests/test_omniroute_broker_policy.py`: verify P-class filtering and allowlist enforcement.
- Update `scripts/smoke_router_providers.py` default provider list to include `omniroute`.
- Add a CI-lite smoke that skips if `localhost:20128` is not reachable.

### Slice 9 — Rollout and monitoring

- Add `OMNIROUTE_ENABLED` env flag defaulting to `true`.
- In observability, log `provider=omniroute`, `model`, `free_tier=true`, `gateway_reachable`.
- Add a dashboard KPI for free-token savings vs paid routes.
- Document runbook: "OmniRoute gateway down -> harness auto-falls back to OpenRouter."

## Decisions made

1. **Allowlist, not `auto` default.** The harness uses a hardcoded allowlist of known free model IDs in `config/routing/omniroute-models.yaml`. `auto` is available as an opt-in alias only. This keeps routing reproducible and governed.
2. **Chat-only for slice 1.** Embeddings and images are not wired into the router yet; they can be added once the chat path is proven.
3. **No background service auto-install.** `scripts/install_omniroute.py` checks/validates and runs the install only with `--install`. It never starts a persistent service without explicit user action.
4. **Reuse `type: local`.** OmniRoute is classified as `type: local` in `providers.yaml` for billing-axis purposes (Axis F, free local), but it is added to `_CLOUD_ROUTING_PROVIDERS` in `provider_selector.py` for privacy filtering.
5. **P0/P1 default, P2 opt-in, P3/P4/P5 block.** Same privacy posture as OpenRouter.
6. **Rank below direct providers, above OpenRouter.** OmniRoute is a free fallback, not the primary route.

## Open questions

## Suggested execution order

1. **Slice 1 + Slice 2 + Slice 3** → working adapter with manual gateway start.
2. **Slice 6** → policy signed off.
3. **Slice 4 + Slice 5** → model allowlist and routing-table wiring.
4. **Slice 8** → tests + smoke.
5. **Slice 7** → OpenCode doc.
6. **Slice 9** → observability and rollout.
