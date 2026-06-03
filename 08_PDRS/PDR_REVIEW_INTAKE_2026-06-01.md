# PDR: GitHub Review Intake to Agent Dispatch

| Field | Value |
|---|---|
| PDR ID | PDR-REVIEW-INTAKE-001 |
| System | Chromatic Harness |
| Status | Implemented & Proven (epic tmx5; see docs/pdr/review_intake/ACCEPTANCE_PROOF.md) |
| Owner | Human / Chromatic Orchestrator |
| Created | 2026-06-01 |
| Version | 0.1.0 |
| Target Repos | Any GitHub repo using Chromatic Harness queue standards |

## 1. Executive Summary

Build a GitHub review-intake system that automatically converts reviewer feedback, inline PR comments, issue comments, and CI/check failures into structured, confidence-scored work items for agents and subagents.

The system must be event-driven, queue-first, auditable, and collision-safe. Agents should never wander across GitHub looking for work. They should consume governed queue items with scoped files, acceptance checks, confidence scores, and stop conditions.

## 2. Problem

Current PR review feedback can become scattered across:

- inline review comments
- general PR comments
- requested changes summaries
- CI failures
- unresolved review threads
- IDE terminals
- multiple agent/subagent sessions

Without a normalized intake path, agents will duplicate work, miss reviewer comments, overreach into unrelated files, or collide on the same PR branch.

## 3. Goals

1. Ingest GitHub review activity automatically.
2. Normalize all review signals into `review_finding` records.
3. Deduplicate repeated or stale review feedback.
4. Classify each finding by type, risk, severity, and agent fit.
5. Create or update `next-work.queue.json` items.
6. Dispatch only ready, scoped, confidence-gated work.
7. Enforce one mutating agent per PR branch.
8. Require validation evidence before resolution.
9. Comment back on PRs with a consistent resolution format.
10. Log repeated reviewer patterns into learning artifacts.

## 4. Non-Goals

- Do not auto-merge PRs.
- Do not bypass human gates for security, architecture, secrets, production deployment, or irreversible changes.
- Do not allow broad repo refactors from vague review comments.
- Do not allow multiple agents to mutate the same PR branch simultaneously.
- Do not replace human reviewer judgment.

## 5. Architecture

```text
GitHub PR / Review / CI Event
        ↓
GitHub Action or GitHub App
        ↓
Review Intake Collector
        ↓
review_finding JSONL
        ↓
Classifier + Confidence Gate
        ↓
next-work.queue.json
        ↓
Queue Dispatcher
        ↓
Assigned Agent Mission Packet
        ↓
Scoped Patch + Validation
        ↓
PR Resolution Comment
        ↓
Resolution Log + Learning Log
```

## 6. Event Sources

| Source | Event | Reason |
|---|---|---|
| PR review | `pull_request_review` | Capture approval, changes requested, dismissed/edited reviews |
| Inline review comment | `pull_request_review_comment` | Most precise source for code-level fixes |
| PR/issue comment | `issue_comment` | Capture broader reviewer instructions |
| CI/check run | `check_run` | Convert failing checks into queue items |
| Workflow completion | `workflow_run` | Convert failed automation into queue items |
| PR synchronize | `pull_request.synchronize` | Invalidate stale findings after new commits |

## 7. Data Contracts

Primary artifacts:

- `review_finding`: normalized reviewer/CI issue
- `next_work_item`: dispatchable work unit
- `agent_dispatch`: assigned agent execution record
- `pr_branch_lock`: mutation lock preventing collision
- `review_resolution`: evidence that the finding was handled

Schemas live in `schemas/`.

## 8. Confidence Gate

Each finding receives a confidence score from 0 to 100.

| Band | Action |
|---:|---|
| 90-100 | Auto-patch allowed if scoped and reversible |
| 75-89 | Auto-patch allowed with validation |
| 60-74 | Draft or plan only unless low risk |
| 40-59 | Investigation task only |
| 0-39 | Blocked / needs human or reviewer clarification |

Formula:

```text
confidence =
  actionability * 0.25 +
  file_scope_clarity * 0.20 +
  testability * 0.20 +
  risk_safety * 0.15 +
  dedupe_certainty * 0.10 +
  agent_fit * 0.10
```

## 9. Finding Classification

| Class | Default Agent | Auto-Fix Default |
|---|---|---|
| lint_style | Janitor / Sentinel | Yes |
| test_failure | Auditor / Sentinel | Yes, if scoped |
| bug_fix | Sentinel | Yes, with tests |
| security | Sentinel | Human gate may be required |
| architecture | Archivist / Auditor | Usually plan first |
| docs | Archivist | Yes |
| repo_hygiene | Janitor | Yes |
| unclear | Auditor | No |

## 10. Collision Control

Rule: one PR branch gets one active mutating agent.

- Multiple agents may inspect.
- Only one agent may patch.
- Locks must expire.
- Stale locks can be released by the orchestrator.
- If a lock exists, new mutation work becomes blocked or queued.

## 11. Required Files

```text
.github/workflows/review-intake.yml
.github/workflows/harness-review-intake-check.yml
scripts/review_intake.py
scripts/classify_review_finding.py
scripts/update_next_work_queue.py
scripts/post_review_resolution.py
scripts/lock_pr_branch.py
scripts/dispatch_review_work.py
scripts/review_learning.py
schemas/review_finding.schema.json
schemas/next_work_item.schema.json
schemas/agent_dispatch.schema.json
schemas/pr_branch_lock.schema.json
schemas/review_resolution.schema.json
07_LOGS_AND_AUDIT/review_intake/findings.jsonl
07_LOGS_AND_AUDIT/review_intake/queue.json
07_LOGS_AND_AUDIT/review_intake/state.json
07_LOGS_AND_AUDIT/review_intake/dispatch_log.jsonl
07_LOGS_AND_AUDIT/review_intake/resolution_log.jsonl
07_LOGS_AND_AUDIT/review_intake/reviewer_patterns.jsonl
04_PLAYBOOKS/REVIEW_INTAKE_PLAYBOOK.md
04_PLAYBOOKS/REVIEW_DISPATCH_PLAYBOOK.md
04_PLAYBOOKS/REVIEW_RESOLUTION_PLAYBOOK.md
04_PLAYBOOKS/PR_COLLISION_CONTROL_PLAYBOOK.md
04_PLAYBOOKS/REVIEW_LEARNING_PLAYBOOK.md
docs/pdr/review_intake/
```

> **Portable PDR zip paths** (`00_PLANNING/`, `02_LOGS/`, `03_PLAYBOOKS/`) are scaffold-only.
> Do not create them in this repo. See `CHROMATIC_TREES.md` §4 and
> `07_LOGS_AND_AUDIT/audits/repo_reorg_audit_2026-06-01.md`.

## 12. Implementation Phases

### Phase 1: Passive Intake

- Capture GitHub review-comment events.
- Write normalized findings to JSONL.
- Do not patch yet.

### Phase 2: Queue Creation

- Classify findings.
- Create or update queue items.
- Apply dedupe keys.

### Phase 3: Agent Pickup

- Dispatcher chooses ready work.
- Agent receives mission packet.
- Agent patches only allowed files.

### Phase 4: Resolution Comment

- Agent posts evidence summary.
- Queue item is marked done or blocked.
- Finding is marked resolved or needs follow-up.

### Phase 5: Central Collector

- Promote from repo-local GitHub Action to central GitHub App.
- Add cross-repo dashboard and SQLite storage.

## 13. Acceptance Criteria

- [ ] GitHub review events create valid `review_finding` records.
- [ ] Duplicate comments do not create duplicate queue items.
- [ ] Queue items include owner agent, priority, risk, confidence, links, and acceptance checks.
- [ ] Agent mission packets are generated from queue items.
- [ ] Branch mutation locks prevent double-patching.
- [ ] Resolution comments include files changed and validation evidence.
- [ ] Security/architecture/unclear findings are gated instead of blindly patched.
- [ ] Logs support audit and learning review.

## 14. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Duplicate findings | Agent rework | Dedupe key and stale-event checks |
| Vague review comments | Bad patches | Confidence gate and reviewer clarification status |
| Multi-agent collision | Broken PR branch | PR branch lock |
| Overbroad fixes | Repo churn | Allowed files and stop conditions |
| CI noise | Queue spam | Failure grouping and dedupe by workflow/check/path |
| Security-sensitive changes | Unsafe mutation | Human gate |

## 15. Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-06-01 | Use queue-first dispatch | Keeps agents bounded and auditable |
| 2026-06-01 | Use JSONL for findings/logs | Append-only, easy audit, low friction |
| 2026-06-01 | Start with GitHub Action | Faster MVP than GitHub App |
| 2026-06-01 | Require branch locks | Prevents IDE/agent collisions |

## 16. Open Questions

1. Which repo should be the central Command-Center source of truth?
2. Should the first implementation commit queue changes directly, or open a PR?
3. Which agents are enabled for auto-patch on day one?
4. Which CI checks are mandatory acceptance checks per repo?
5. Should review resolution comments be posted automatically or drafted first?

## 17. Recommended Next Work

1. Implement Phase 1 passive intake in a single test repo.
2. Run fake GitHub event payloads through `scripts/review_intake.py`.
3. Validate schemas.
4. Connect queue-dispatcher agent to consume `next-work.queue.json`.
5. Enable branch lock before allowing mutation.
