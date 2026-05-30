# OpenRouter Broker Policy

## Purpose

OpenRouter provides a multi-model cloud routing layer. In Chromatic Harness v2, OpenRouter is governed as a broker/fallback layer, not an unrestricted provider.

This policy defines when OpenRouter may be used, which privacy classes it may handle, how costs are controlled, and what must be logged.

---

## Role in Routing Stack

Preferred route order:

```text
1. Local Ollama / LM Studio when sufficient
2. Remote Ollama desktop over LAN when available
3. Direct provider API when configured and policy-approved
4. OpenRouter broker fallback
5. Premium/RunPod when justified
```

OpenRouter is useful when:

- direct provider key is unavailable
- model diversity is needed
- a cheaper equivalent model exists
- routing wants a fallback without hardcoding each provider
- testing alternate models for a task class

---

## Privacy Classes

| Privacy Class | Meaning | OpenRouter Allowed? |
|---|---|---:|
| P0 | Public docs/examples | Yes |
| P1 | Non-sensitive repo content | Yes, if allowed by repo policy |
| P2 | Internal project logic | Conditional |
| P3 | Proprietary architecture | Human approval recommended |
| P4 | Secrets, credentials, private personal data | No |
| P5 | Regulated / highly sensitive / client confidential | No |

OpenRouter must not receive secrets, credentials, tokens, private keys, or raw high-sensitivity data.

---

## Complexity Routing

| Complexity | OpenRouter Role |
|---|---|
| C1 | Usually unnecessary; use local. |
| C2 | Allowed as fallback when local/direct API unavailable or context too large. |
| C3 | Allowed for selected model families if privacy permits. |
| C4 | Allowed only when selected model is explicitly suitable and budget permits. |

---

## Speed Modes

| Mode | OpenRouter Behavior |
|---|---|
| low | Block unless explicitly overridden. |
| balance | Fallback only when local/direct route insufficient. |
| speed | Allowed when it improves latency or capability. |

---

## Model Allowlist

Maintain an explicit allowlist in:

```text
09_DEPLOYMENT/config/routing/openrouter-models.yaml
```

Suggested fields:

```yaml
models:
  - id: anthropic/claude-sonnet
    allowed_complexity: [C3, C4]
    max_privacy: P2
    notes: "Use for reasoning when direct Anthropic unavailable."

  - id: google/gemini-flash
    allowed_complexity: [C2, C3]
    max_privacy: P2
    notes: "Cheap broad context fallback."

  - id: openai/gpt-4o-mini
    allowed_complexity: [C1, C2]
    max_privacy: P2
    notes: "Cheap structured tasks."
```

Do not route to unknown OpenRouter models without adding them to the registry.

---

## Cost Controls

Each OpenRouter request must include:

- model id
- estimated input tokens
- estimated output tokens
- expected max cost
- task complexity
- privacy class
- fallback reason

Recommended hard stops:

| Scope | Default Cap |
|---|---:|
| Single C1/C2 task | $0.05 |
| Single C3 task | $0.25 |
| Single C4 task | $1.00 |
| Daily OpenRouter budget | configurable |
| Weekly OpenRouter budget | configurable |

If cost cannot be estimated, require human approval for C3/C4.

---

## Logging Requirements

Log every OpenRouter call to the execution audit stream.

Required fields:

```json
{
  "timestamp": "",
  "mission_id": "",
  "bead_id": "",
  "provider": "openrouter",
  "model": "",
  "complexity": "C2",
  "privacy_class": "P1",
  "speed_mode": "balance",
  "fallback_reason": "direct provider unavailable",
  "estimated_cost": 0.0,
  "actual_cost": null,
  "input_tokens": null,
  "output_tokens": null,
  "result_status": "success"
}
```

---

## Fallback Rules

OpenRouter may be selected when:

- local route unavailable or insufficient
- remote Ollama unreachable
- direct provider key missing/unhealthy
- selected OpenRouter model is allowlisted
- privacy class is permitted
- cost cap is respected

OpenRouter must not be selected when:

- task includes secrets or credentials
- privacy class is P4/P5
- model is not allowlisted
- budget cap exceeded
- local/offline mode is required
- direct provider is healthier and cheaper for same model

---

## Failure Handling

If OpenRouter fails:

1. Log failure.
2. Retry once only if failure is transient.
3. Fall back to next allowed provider.
4. Mark bead blocked if all routes fail.
5. Create alert bead if repeated provider failure occurs.

---

## Implementation (repo today)

| Concern | Location | Notes |
|---------|----------|-------|
| Provider registry | `config/routing/providers.yaml` | `openrouter` entry: `privacy_max: P1`, `cost_tier: low` |
| Selection logic | `02_RUNTIME/router/provider_selector.py` | Matrix tests in `tests/test_complexity_and_routing.py` |
| Privacy classes | `09_DEPLOYMENT/config/routing/privacy_policy.yaml` (if present) | P4/P5 hard blocks may be policy-only — verify in ROUTE-006 |
| Context / pre-session | `scripts/session_context_report.py`, `scripts/audit_mcp_context.py` | Not OpenRouter-specific |

**Gaps (track in beads epic `chromatic-harness-v2-gh1`, child `15x.5`):**

- `openrouter-models.yaml` allowlist not yet in repo
- Dedicated `test_openrouter_broker_policy.py` not present
- P4/P5 cloud block enforcement vs policy-only — audit ROUTE-005 / ROUTE-006

---

## Implementation Targets (planned)

```text
09_DEPLOYMENT/config/routing/openrouter-models.yaml
02_RUNTIME/router/adapters/openrouter.py
02_RUNTIME/router/policies/privacy_gate.py
02_RUNTIME/router/policies/cost_gate.py
tests/test_openrouter_broker_policy.py
```

---

## Canonical Rule

OpenRouter expands capability. It does not bypass governance.
