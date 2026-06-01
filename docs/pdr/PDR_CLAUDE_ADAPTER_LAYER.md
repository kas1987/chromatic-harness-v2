# PDR: Claude Adapter Layer Governance

## 0. Metadata

| Field | Value |
|---|---|
| PDR Name | Claude Adapter Layer Governance |
| Repo | `kas1987/chromatic-harness-v2` |
| Priority | P0 |
| Primary Issue | #99 |
| Duplicate to Close | #100 |
| Status | Proposed |
| Owner | Human / Harness Orchestrator |
| Created | 2026-06-01 |

## 1. Executive Summary

The Chromatic Harness has matured into the actual workflow engine. Claude workflow/slash commands should no longer contain independent orchestration logic. They should become thin adapters that call or summarize harness-controlled scripts, queues, gates, and artifacts.

The goal is to prevent Claude from becoming a second unsupervised orchestrator while still preserving the convenience of slash commands for human interaction.

## 2. Problem

Claude commands can be useful, but if they decide work, mutate files, ship code, or bypass gates independently, they create:

- duplicate authority;
- inconsistent decisions;
- hidden autonomy;
- collision risk;
- skipped verifier gates;
- unlogged state transitions;
- fragile behavior tied to a single chat session.

## 3. Decision

Claude slash commands are adapters only.

Authority hierarchy:

```text
Human
  -> GitHub Issues / bd Queue
  -> Harness Router
  -> Confidence Gate
  -> Lease / Collision Gate
  -> Verifier Gate
  -> workflow_git.py
  -> CI Governance
  -> Release Readiness

Claude Commands
  -> Adapter only
```

## 4. Scope

### In Scope

- Claude slash command governance.
- Command-to-script mapping.
- Adapter validation.
- Forbidden command behaviors.
- Emergency recovery boundaries.
- Telemetry/logging expectations.

### Out of Scope

- Replacing existing harness scripts.
- Rewriting Claude Code internals.
- Allowing Claude commands to become primary orchestration.
- Auto-merging without existing gates.

## 5. Required Files

```text
docs/governance/CLAUDE_WORKFLOW_ADAPTER_POLICY.md
docs/governance/CLAUDE_COMMAND_MATRIX.md
docs/governance/CLAUDE_AUTHORITY_MODEL.md
docs/governance/CLAUDE_RECOVERY_PROCEDURES.md
docs/governance/CLAUDE_COMMAND_SPEC.md
config/claude_command_registry.yaml
config/claude_adapter_rules.yaml
scripts/validate_claude_adapter_policy.py
tests/test_claude_adapter_policy.py
examples/slash_go.md
examples/slash_audit.md
examples/slash_ship.md
examples/slash_recover.md
examples/slash_status.md
queue/claude_adapter_next_work.queue.json
issues/claude_adapter_issue_map.md
registry/claude_adapter_manifest.json
```

## 6. Acceptance Criteria

- [ ] Policy states Claude commands are adapters only.
- [ ] Allowed command matrix exists.
- [ ] Each allowed command maps to a harness authority.
- [ ] Forbidden behaviors are explicit.
- [ ] YAML registry validates.
- [ ] Validator detects command authority violations.
- [ ] Tests pass.
- [ ] Issue #100 is closed as duplicate of #99.
- [ ] CI can run validator without local services.

## 7. Implementation Plan

### Phase 1: Governance Docs

Create policy, authority model, command matrix, recovery procedures, and command spec.

### Phase 2: Machine-Readable Registry

Create YAML command registry and adapter rules so future validators can detect drift.

### Phase 3: Validation

Add `validate_claude_adapter_policy.py` and tests.

### Phase 4: Queue Integration

Add queue items for implementation, duplicate issue cleanup, CI integration, and command telemetry.

## 8. Risks

| Risk | Severity | Mitigation |
|---|---:|---|
| Claude command duplicates harness logic | High | Registry forbids direct orchestration authority |
| Slash command bypasses verifier | Critical | `/ship` must call `workflow_git.py` with verifier requirement |
| Recovery command mutates state unsafely | High | `/recover` defaults to inspect; mutation requires lease/recovery policy |
| Registry drifts from actual commands | Medium | CI validator |

## 9. Done Definition

This PDR is complete when Claude slash commands are reduced to a governed adapter layer and all authority decisions remain inside harness scripts, queues, CI, and verifier gates.
