# OmniRoute Broker Policy

## Purpose

OmniRoute is a **local free-tier gateway** that exposes an OpenAI-compatible
endpoint at `http://localhost:20128/v1`. It aggregates free tiers and low-cost
pools from 290 providers into one local endpoint. In Chromatic Harness v2,
OmniRoute is governed as a **free local gateway**, not a direct cloud provider
or an unrestricted broker.

This policy defines when OmniRoute may be used, which privacy classes it may
handle, how it is ranked, and what must be logged.

---

## Role in Routing Stack

Preferred route order:

```text
1. Local Ollama / LM Studio / native_claude
2. Remote Ollama over LAN
3. Direct provider API when configured and policy-approved
4. OmniRoute local free gateway
5. OpenRouter broker fallback
6. Premium/RunPod when justified
```

OmniRoute is ideal when:

- a task is P0/P1 (public or non-sensitive repo content).
- direct provider keys are missing, exhausted, or should be conserved.
- a low-cost/free model is sufficient for the task class.
- OpenCode or another local-first tool needs a free backend.

---

## Privacy Classes

| Privacy Class | Meaning | OmniRoute Allowed? |
|---|---|---:|
| P0 | Public docs/examples | Yes |
| P1 | Non-sensitive repo content | Yes, default |
| P2 | Internal project logic | Conditional — require explicit `omniroute_p2: true` preference |
| P3 | Proprietary architecture | No |
| P4 | Secrets, credentials, private personal data | No |
| P5 | Regulated / highly sensitive / client confidential | No |

OmniRoute must not receive secrets, credentials, tokens, private keys, or raw
high-sensitivity data. Although the gateway runs on localhost, it still forwards
to third-party free providers, so the privacy posture matches a broker/cloud
provider.

---

## Complexity Routing

| Complexity | OmniRoute Role |
|---|---|
| C1 | Free fast models (`oc/deepseek-v4-flash-free`) for trivial tasks. |
| C2 | Free coding models (`oc/qwen3-coder-free`) for routine codegen/review. |
| C3 | Reasoning models (`oc/deepseek-r1-free`) only when direct providers are unavailable. |
| C4 | Reasoning models (`oc/kimi-k2-thinking-free`) as a last resort before OpenRouter. |

OmniRoute is **not** the default for any complexity class. It is ranked below
direct frontier providers and above OpenRouter in the routing table.

---

## Speed Modes

| Mode | OmniRoute Behavior |
|---|---|
| low | Blocked unless explicitly overridden. Local-only routes win. |
| balance | Allowed as a free fallback after local/direct routes. |
| speed | Allowed when it improves latency or when direct providers are slow. |

---

## Model Allowlist

Maintain an explicit allowlist in:

```text
config/routing/omniroute-models.yaml
```

Only models listed there may be selected. The default allowlist includes known
free-tier IDs from the OpenCode Free pool and deterministic `auto/*` variants.
The catch-all `auto` model is available only as an opt-in alias because it is
non-deterministic.

Do not route to unknown OmniRoute models without adding them to the registry.

---

## Cost Controls

OmniRoute is free from CHV2's budget perspective. Every OmniRoute request is
booked under billing axis `F` (free local). Logging still requires:

- model id
- estimated input/output tokens
- task complexity
- privacy class
- fallback reason

Recommended soft limits:

| Scope | Default Cap |
|---|---:|
| Single P0/P1 task | 8K output tokens |
| Daily OmniRoute token budget | configurable per deployment |
| OmniRoute as primary provider | never; it is always a fallback/free tier |

---

## Logging Requirements

Log every OmniRoute call to the execution audit stream.

Required fields:

```json
{
  "timestamp": "",
  "mission_id": "",
  "bead_id": "",
  "provider": "omniroute",
  "model": "",
  "complexity": "C2",
  "privacy_class": "P1",
  "speed_mode": "balance",
  "fallback_reason": "direct provider unavailable",
  "estimated_cost": 0.0,
  "actual_cost": 0.0,
  "input_tokens": 0,
  "output_tokens": 0,
  "result_status": "success",
  "free_tier": true
}
```

---

## Fallback Rules

OmniRoute may be selected when:

- local routes are unavailable or insufficient for the task.
- direct provider keys are missing/unhealthy.
- the selected OmniRoute model is in the allowlist.
- privacy class is P0/P1 (or P2 with explicit opt-in).
- the gateway at `localhost:20128` is reachable.

OmniRoute must not be selected when:

- task includes secrets or credentials.
- privacy class is P3/P4/P5.
- model is not in the allowlist.
- local/offline mode is required.
- a direct provider is healthier and cheaper for the same model.

If OmniRoute fails, the harness falls back to the next provider in the ranked
list (typically OpenRouter or a direct provider).

---

## Failure Handling

If OmniRoute fails:

1. Log failure.
2. Retry once only if failure is transient.
3. Fall back to next allowed provider.
4. Mark bead blocked if all routes fail.
5. Create alert bead if repeated gateway failure occurs.

---

## Implementation (repo today)

| Concern | Location | Notes |
|---------|----------|-------|
| Provider registry | `config/routing/providers.yaml` | `omniroute` entry: `type: local`, `privacy_max: P1`, `cost_tier: free` |
| Adapter | `02_RUNTIME/router/adapters/omniroute_adapter.py` | OpenAI-compatible; dummy key default `sk_omniroute` |
| Adapter registry | `02_RUNTIME/router/adapters/adapters.yaml` | Maps `omniroute` to `OmniRouteAdapter` |
| Selection logic | `02_RUNTIME/router/provider_selector.py` | P1 ceiling + allowlist enforcement |
| Model allowlist | `config/routing/omniroute-models.yaml` | Non-listed models dropped at selection time |
| Billing axis | `02_RUNTIME/router/billing_axis.py` | `omniroute` → Axis F (free local) |
| Routing table | `config/routing/routing-table.yaml` | Inserted below direct providers, above OpenRouter |
| Tests | `tests/test_omniroute_broker_policy.py` | Privacy + allowlist coverage |

---

## Canonical Rule

OmniRoute expands free capability. It does not bypass governance.
