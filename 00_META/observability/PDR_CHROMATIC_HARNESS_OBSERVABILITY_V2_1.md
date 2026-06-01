# PDR: Chromatic Harness Observability + Error Intelligence v2.1

## 0. Executive Summary

v2.1 upgrades the Observability Harness from a passive logging scaffold into an implementation-ready subsystem. It adds active file claim/release controls, command execution wrappers, event routing, queue integration, stronger schema validation, Git state snapshots, IDE tasks, Git hook templates, CI checks, report generation, and bootstrap installation.

## 1. Problem

The Harness operates across multiple IDEs, terminals, agents, and worktrees. Without durable observability and collision controls, errors disappear into session history, agents repeat known mistakes, multiple tools overwrite the same files, and failures do not become structured remediation work.

## 2. Goals

- Capture errors and operational events as structured JSONL.
- Redact secrets before persistence.
- Validate events against stable enums and required fields.
- Prevent multi-agent file collisions using active writer claims.
- Route critical/high events to incidents, collisions, or remediation queue items.
- Wrap terminal commands so failed commands are logged automatically.
- Snapshot Git state before/after risky operations.
- Provide VS Code tasks, Git hook templates, and GitHub Actions checks.
- Generate human-readable observability reports.
- Feed repeated patterns into learnings and fix patterns.

## 3. Deliverables

| Deliverable | Path | Purpose |
|---|---|---|
| Event Schema | `00_META/observability/HARNESS_EVENT_SCHEMA.json` | Source of truth for event records |
| Logger | `scripts/log_harness_event.py` | Append JSONL events |
| Schema Validator | `scripts/validate_event_schema.py` | Enforce required fields and enums |
| Command Wrapper | `scripts/harness_run.py` | Run commands and log failures |
| Claim/Release Tools | `scripts/claim_files.py`, `scripts/release_files.py` | Prevent concurrent writes |
| Router | `scripts/route_event.py` | Promote events to incident/collision/queue outputs |
| Secret Scanner | `scripts/scan_for_secrets.py` | Detect likely secrets before commit/package |
| Git Snapshot | `scripts/snapshot_git_state.py` | Record branch, commit, dirty files |
| Report Generator | `scripts/generate_observability_report.py` | Summarize status and risks |
| Bootstrap | `scripts/bootstrap_observability.py` | Install/initialize Harness files |
| Queue | `00_META/queues/ERROR_REMEDIATION_QUEUE.md` | Turn failures into work |
| CI | `.github/workflows/harness-observability-check.yml` | Prevent observability drift |
| IDE Tasks | `.vscode/tasks.json` | Make commands easy in IDE |
| Git Hooks | `git_hooks/pre-commit`, `git_hooks/pre-push` | Optional local enforcement |

## 4. Architecture

```text
IDE / terminal / agent / CI
  -> harness_run.py or log_harness_event.py
  -> redact_secrets.py
  -> HARNESS_EVENT_SCHEMA validation
  -> ERROR_LOG.jsonl
  -> route_event.py
      -> INCIDENT_LOG.md
      -> COLLISION_REGISTER.md
      -> ERROR_REMEDIATION_QUEUE.md
      -> LEARNINGS_LOG.md candidates
  -> report generator / queue dispatch / playbook updates
```

## 5. Operating Loop

```text
Observe -> Claim Files -> Snapshot Git -> Execute -> Log -> Route -> Validate -> Release Files -> Report -> Learn
```

## 6. Acceptance Criteria

- A failed wrapped command creates an event with non-zero exit code.
- A second writer cannot claim an already claimed file unless `--force` is used.
- A critical event creates or appends to `INCIDENT_LOG.md`.
- A file collision creates or appends to `COLLISION_REGISTER.md`.
- A medium/high/critical event creates a remediation queue item.
- Invalid severity/category/status fails validation.
- GitHub Action validates scripts and logs.
- The zip excludes `__pycache__`, `.pyc`, and generated cache artifacts.

## 7. Rollout Plan

1. Drop in bundle.
2. Run `python scripts/bootstrap_observability.py --repo-root .`.
3. Use `harness_run.py` for risky commands.
4. Require agents to claim/release files.
5. Enable Git hooks and GitHub Actions.
