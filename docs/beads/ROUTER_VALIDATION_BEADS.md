# Router Validation Beads

## Purpose

Reference backlog for Harness v2 router and pre-session validation.

| Epic | Scope |
|------|--------|
| `chromatic-harness-v2-15x` | Umbrella (legacy import) |
| `chromatic-harness-v2-gh1` | ROUTE-001, 002, 003, 005, 006 (`15x.1`–`15x.3`, `15x.5`, `15x.6`) |
| `chromatic-harness-v2-uum` | ROUTE-004, 007 (extended), 008 (`15x.4`, `15x.8`) |

Pre-session **manifest** (base ROUTE-007) ships with `scripts/pre_session_manifest.py`. Extended routing fields remain on router-p2.

Use `bd show chromatic-harness-v2-gh1` for live status.

---

## ROUTE-001: Validate Runtime Context Detector

**Priority:** p1  
**Area:** router/context  
**Owner:** Auditor / Builder

### Objective
Add tests proving the runtime context detector correctly identifies laptop, desktop, GPU, VRAM, connectivity, Ollama, remote Ollama, LM Studio, power source, and memory pressure.

### Acceptance Criteria
- [ ] Laptop/no-GPU context test passes.
- [ ] Desktop/RTX 4070 context test passes.
- [ ] Ollama localhost probe is tested.
- [ ] Remote Ollama probe is tested with mocked reachable/unreachable states.
- [ ] Offline connectivity state is tested.
- [ ] Context output is serializable to pre-session manifest.

### Suggested command

```bash
bd create "ROUTE-001: Validate Runtime Context Detector" --priority p1
```

---

## ROUTE-002: Build Complexity Classifier 50-Case Suite

**Priority:** p1  
**Area:** router/classifier  
**Owner:** Auditor

### Objective
Create a 50-case test suite for task complexity classification across C1-C4.

### Acceptance Criteria
- [ ] At least 10 C1 cases.
- [ ] At least 15 C2 cases.
- [ ] At least 15 C3 cases.
- [ ] At least 10 C4 cases.
- [ ] Edge cases documented.
- [ ] False-positive cases included.

---

## ROUTE-003: Validate Provider Selector Matrix

**Priority:** p1  
**Area:** router/provider-selector  
**Owner:** Builder / Auditor

### Objective
Test provider selection across C-level, speed mode, privacy class, runtime context, and availability.

### Required Matrix

| Dimension | Values |
|---|---|
| Complexity | C1, C2, C3, C4 |
| Speed mode | low, balance, speed |
| Runtime | laptop, desktop, laptop+remote desktop, offline |
| Privacy | P0, P1, P2, P3, P4, P5 |
| Connectivity | full, limited, offline |

### Acceptance Criteria
- [ ] Local-first routing works.
- [ ] Remote Ollama preferred when reachable and suitable.
- [ ] Cloud blocked for P4/P5.
- [ ] OpenRouter selected only when policy permits.
- [ ] Premium providers require justified complexity/capability.

---

## ROUTE-004: Validate Remote Ollama Probe

**Priority:** p2  
**Area:** router/ollama  
**Owner:** Builder

### Objective
Implement and test LAN remote Ollama detection for desktop GPU routing.

### Acceptance Criteria
- [ ] `desktop.local:11434` probe supported.
- [ ] IP-based endpoint config supported.
- [ ] `/api/tags` response parsed.
- [ ] Latency measured.
- [ ] Endpoint marked unavailable when sleeping/offline.
- [ ] Provider selector prefers remote Ollama for C2/C3 when suitable.

---

## ROUTE-005: Implement OpenRouter Broker Policy

**Priority:** p1  
**Area:** router/openrouter  
**Owner:** Sentinel / Builder

### Objective
Formalize OpenRouter routing with allowlist, privacy classes, fallback reason, and cost logging.

### Acceptance Criteria
- [ ] `OPENROUTER_BROKER_POLICY.md` is linked from routing docs.
- [ ] `openrouter-models.yaml` exists.
- [ ] P4/P5 privacy classes are blocked.
- [ ] Non-allowlisted models are blocked.
- [ ] Cost cap is enforced.
- [ ] OpenRouter calls are logged to execution audit.

---

## ROUTE-006: Validate Privacy Gate for Cloud Providers

**Priority:** p1  
**Area:** governance/privacy  
**Owner:** Sentinel

### Objective
Ensure cloud provider routing respects privacy classes.

### Acceptance Criteria
- [ ] P0-P2 route according to policy.
- [ ] P3 requires conditional approval or explicit policy allowance.
- [ ] P4/P5 blocked from OpenRouter and cloud APIs.
- [ ] Secrets detection triggers stop condition.
- [ ] Tests cover OpenAI, Gemini, Claude, OpenRouter, Featherless, RunPod.

---

## ROUTE-007: Generate Pre-Session Manifest

**Priority:** p1  
**Area:** pre-session/context  
**Owner:** Auditor / Builder

### Objective
Generate a compact machine-readable manifest at session start.

### Acceptance Criteria
- [ ] Manifest includes branch, git status, active beads, handoff pointer, MCP profile, context tier.
- [ ] Manifest includes runtime routing context.
- [ ] Manifest excludes bulk logs and archives.
- [ ] Manifest can be written to `07_LOGS_AND_AUDIT/pre_session/`.

---

## ROUTE-008: Enforce MCP Context Budget Test

**Priority:** p2  
**Area:** mcp/context  
**Owner:** Sentinel / Auditor

### Objective
Ensure MCP context hygiene remains enforced before long sessions.

### Acceptance Criteria
- [ ] MCP audit command runs in pre-session flow.
- [ ] Heavy MCPs are flagged.
- [ ] Strict mode fails when token budget exceeded.
- [ ] Daily harness profile remains lean.
