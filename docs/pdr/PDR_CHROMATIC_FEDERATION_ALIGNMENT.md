# PDR: Chromatic Federation Alignment

## 0. Metadata

| Field | Value |
|---|---|
| PDR | Chromatic Federation Alignment |
| Status | Draft |
| Owner | Chromatic Harness |
| Primary Repo | `kas1987/chromatic-harness-v2` |
| Related Repos | `chromatic-wiki`, `chromatic-stack`, `claude-config`, `Chromatic_Brain`, `ChromaticSystems` |
| Priority | P0 |
| Risk | T2-T3 |

## 1. Executive Summary

The Chromatic ecosystem has split into several specialized repositories. That separation is useful, but the repos now need a clear authority model so old sources of truth do not compete with `chromatic-harness-v2`.

This PDR establishes `chromatic-harness-v2` as the execution authority, while preserving the other repos as federated support systems:

| Repo | Role |
|---|---|
| `chromatic-harness-v2` | Runtime execution, governance gates, queue/issue execution, CI, release readiness |
| `chromatic-wiki` | Durable canon, promoted playbooks, reviewed learnings |
| `chromatic-stack` | Local service substrate and infrastructure definitions |
| `claude-config` | Claude adapter/config layer only |
| `Chromatic_Brain` | Legacy brain/planning archive and migration source |
| `ChromaticSystems` | Registry, skill catalog, cross-repo governance source |

## 2. Problem

Several repos still contain useful logic, but some may still claim or imply authority over queueing, routing, skills, memory, model selection, or operational behavior. Harness v2 now contains newer governance, health, CI, lease/collision, and workflow logic. Without federation, the ecosystem risks:

- duplicate sources of truth;
- stale Claude workflow assumptions;
- legacy queue conflicts;
- skill catalog drift;
- unclear promotion path from runtime learning to durable canon;
- repo-specific governance divergence.

## 3. Goals

1. Define one source of truth per domain.
2. Preserve useful separated repos without merging everything.
3. Create a machine-readable repo role registry.
4. Define sync and promotion flows between repos.
5. Identify legacy logic that must be migrated, archived, or demoted.
6. Prevent old repos from bypassing Harness v2 authority.

## 4. Non-Goals

- This PDR does not migrate all files immediately.
- This PDR does not delete any repo.
- This PDR does not make Wiki or Brain the runtime authority.
- This PDR does not bypass existing Harness v2 governance gates.

## 5. Current-State Assessment

### 5.1 Harness v2

Harness v2 is the active runtime authority. It owns execution, governance gates, CI, release readiness, health dashboard, workflow git automation, and collision controls.

### 5.2 Chromatic Wiki

Wiki is the durable canon layer. It should receive promoted learnings, stable playbooks, policies, and antipatterns after they are proven in Harness v2.

### 5.3 Chromatic Stack

Stack is the local-first service substrate. It owns infrastructure definitions for LiteLLM, n8n, Langfuse, Open WebUI, OpenHands, Caddy, ComfyUI, vLLM, and Ollama integration.

### 5.4 Claude Config

Claude config is an adapter layer. It may define lightweight slash commands and model routing hints, but it must not duplicate Harness v2 routing, queue, confidence, verifier, lease, collision, or shipping logic.

### 5.5 Chromatic Brain

Brain contains useful historical planning and queue concepts, but it must be demoted from active queue authority unless explicitly federated through Harness v2.

### 5.6 ChromaticSystems

Systems contains useful registries and skill catalog data. It should remain the registry/skill-governance source, but validation and runtime usage should be integrated with Harness v2.

## 6. Authority Model

```text
Human Owner
  -> GitHub Issues / Beads / Queue
  -> chromatic-harness-v2 runtime router
  -> confidence gate
  -> lease/collision gate
  -> verifier gate
  -> workflow_git.py
  -> CI governance
  -> release readiness
  -> promotion to Wiki / Registry
```

Supporting repos may provide inputs, but Harness v2 decides runtime execution.

## 7. Repo Role Registry

A machine-readable registry lives at:

```text
config/repo_role_registry.yaml
```

It defines:

- repo name;
- authority level;
- owned domains;
- forbidden domains;
- sync direction;
- migration status;
- validation checks.

## 8. Sync Flows

### 8.1 Harness to Wiki

```text
runtime learning -> learning bead -> canon candidate -> reviewed Wiki doc
```

Wiki never receives unverified runtime noise.

### 8.2 Stack to Harness

```text
stack service config -> harness health service registry -> health dashboard check
```

Stack defines infrastructure; Harness validates runtime health.

### 8.3 Claude Config to Harness

```text
slash command -> harness script -> artifact/log -> summary
```

Claude commands are adapters only.

### 8.4 Brain to Harness

```text
legacy queue/planning item -> migration triage -> GitHub issue/bead -> Harness queue
```

Brain is a migration source, not active authority.

### 8.5 Systems to Harness

```text
skill catalog/registry -> skill governance report -> Harness health/readiness gate
```

Systems catalogs; Harness enforces operational readiness.

## 9. Implementation Plan

### Phase 0 — Register authority

- Add repo role registry.
- Add schema and validator.
- Add federation authority map.

### Phase 1 — Demote stale authorities

- Update `claude-config` docs to say adapter-only.
- Update `Chromatic_Brain` docs to say legacy/migration source.
- Update `chromatic-wiki` docs to point to Harness v2 promotion flow.

### Phase 2 — Sync useful logic

- Pull skill catalog summaries from `ChromaticSystems` into Harness governance reports.
- Pull service inventory from `chromatic-stack` into Harness health dashboard config.
- Convert Brain queue remnants into GitHub issues/beads.

### Phase 3 — CI enforcement

- Validate `repo_role_registry.yaml`.
- Detect forbidden authority claims.
- Add drift report for repos that conflict with role registry.

## 10. Acceptance Criteria

- [ ] `FEDERATION_AUTHORITY_MAP.md` exists and is clear.
- [ ] `repo_role_registry.yaml` exists and validates.
- [ ] Each repo has exactly one updated role.
- [ ] Legacy authority claims are identified.
- [ ] Sync flows are documented.
- [ ] Validator can fail on missing required fields.
- [ ] Harness v2 remains runtime authority.
- [ ] Wiki remains durable canon only.
- [ ] Claude config remains adapter-only.

## 11. Risks

| Risk | Severity | Mitigation |
|---|---:|---|
| Old repos continue acting as source of truth | High | Authority registry + CI drift checks |
| Useful logic gets lost during demotion | Medium | Migration inventory before archive |
| Claude commands bypass Harness v2 | High | Adapter policy and command registry |
| Skill catalog remains stale | Medium | Systems-to-Harness sync report |
| Stack service list drifts from health dashboard | Medium | Stack-to-Harness service registry sync |

## 12. Best Next Action

Install this package into `chromatic-harness-v2`, then open a P0 issue to implement the registry validator and update each repo README with the new authority model.
