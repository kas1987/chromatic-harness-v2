# PDR: Chromatic Harness Observability + Error Intelligence Layer

## 0. Metadata

| Field | Value |
|---|---|
| PDR Name | Chromatic Harness Observability + Error Intelligence Layer |
| Version | 0.1.0 |
| Status | Draft Implementation Package |
| Owner | Chromatic Harness Human Owner |
| Created | 2026-06-01 |
| Domain | Observability / Error Logging / Collision Control / Learning Feedback |
| Applies To | IDEs, terminals, agents, scripts, CI, repo automation, GO-mode operations |

---

## 1. Executive Summary

Chromatic Harness needs a durable operational memory layer for errors, file collisions, failed commands, agent drift, and repeated debugging patterns. The current system can move quickly across multiple IDEs, terminals, and model agents, but that speed creates a high risk of invisible failures, duplicated fixes, edit collisions, and lost learnings.

This PDR defines a structured event logging and learning system that turns errors into reusable intelligence. Every significant failure is captured as a normalized event, classified by severity and category, linked to the files/tools/agents involved, and routed into one of five outcomes: log only, fix now, queue task, open incident, or update learning.

---

## 2. Problem Statement

Chromatic Harness is operating across several execution surfaces:

- Multiple IDEs and AI coding environments
- Terminals and shell sessions
- Autonomous or semi-autonomous agents
- Repo automation and CI-like workflows
- PDR, playbook, and queue-driven planning

This creates several failure modes:

1. Errors are solved locally but not recorded globally.
2. Agents repeat known mistakes because prior fixes are not discoverable.
3. File collisions happen when two tools edit the same file without awareness.
4. Failed commands do not become structured queue items.
5. Severe events are not consistently escalated into incidents.
6. Lessons learned do not reliably update playbooks.
7. Humans lose confidence because the system cannot explain what broke and why.

---

## 3. Goals

### Primary Goals

1. Create a structured error/event log for all Harness surfaces.
2. Detect and document file collisions from multiple IDEs/agents.
3. Convert repeated errors into reusable fix patterns.
4. Convert serious failures into incidents with human-readable records.
5. Feed learnings back into playbooks, queues, and agent instructions.
6. Support GO-mode by giving agents durable memory and stop conditions.

### Secondary Goals

1. Reduce repeated debugging.
2. Reduce tool-call waste.
3. Improve agent accountability.
4. Improve repo governance.
5. Create audit-ready operational evidence.

---

## 4. Non-Goals

This PDR does not attempt to:

- Replace full observability platforms like Datadog, OpenTelemetry, or Sentry.
- Implement enterprise distributed tracing in v0.1.
- Automatically resolve collisions without human or resolver-agent review.
- Log secrets, raw environment dumps, or sensitive credentials.
- Permit destructive recovery actions without explicit approval.

---

## 5. Design Principles

| Principle | Meaning |
|---|---|
| Log First, Automate Second | Stabilize event shape before heavy automation. |
| Structured Over Vibes | Use schemas, categories, severity, and status fields. |
| Evidence Before Learning | Every learning should link to one or more events. |
| Halt Before Damage | File collisions and critical events stop mutation. |
| Redact By Default | Never persist secrets or sensitive environment values. |
| Smallest Safe Next Step | Errors should create bounded fix tasks, not broad rewrites. |
| Append-Friendly | Use JSONL for raw events to reduce write contention. |
| Human-Readable Summaries | Maintain markdown logs for incidents, collisions, and learnings. |

---

## 6. Proposed Architecture

```txt
Error / Event Source
  -> Redaction
  -> Normalization
  -> Classification
  -> Append to ERROR_LOG.jsonl
  -> Route Outcome
      -> Fix Now
      -> Queue Task
      -> Open Incident
      -> Record Learning
      -> Add Fix Pattern
```

### Event Sources

- Terminal commands
- IDE task runners
- Git hooks
- Agent dispatch runs
- CI/build/test failures
- Manual human notes
- Repo validators
- File collision detector

### Durable Outputs

| Artifact | Purpose |
|---|---|
| ERROR_LOG.jsonl | Machine-readable append-only event stream |
| INCIDENT_LOG.md | Serious human-readable event records |
| COLLISION_REGISTER.md | Multi-writer file conflict tracking |
| LEARNINGS_LOG.md | Durable operational lessons |
| FIX_PATTERN_LIBRARY.md | Known error signatures and fixes |
| OBSERVABILITY_DASHBOARD.md | Human status view |

---

## 7. Event Lifecycle

1. **Capture**: Receive event from terminal, IDE, agent, script, or human.
2. **Redact**: Remove secrets and sensitive values.
3. **Normalize**: Convert to standard Harness event schema.
4. **Classify**: Assign type, category, severity, and status.
5. **Persist**: Append to `ERROR_LOG.jsonl`.
6. **Route**: Decide whether to ignore, fix, queue, incident, or learn.
7. **Link**: Connect event to fix, incident, collision, or learning.
8. **Review**: Summarize patterns and update playbooks.

---

## 8. Severity Model

| Severity | Meaning | Required Action |
|---|---|---|
| info | Operational note | Log only |
| low | Minor warning or recoverable issue | Log, optional learning |
| medium | Failed command, failed test, repeated confusion | Queue fix or investigate |
| high | File collision, broken build, scope breach | Halt affected workflow and assign resolver |
| critical | Secret leak, destructive action, data loss | Incident and human gate |

---

## 9. Event Categories

| Category | Description | Default Route |
|---|---|---|
| tool_failure | CLI/tool/API failed | Retry once, then log |
| file_collision | Multiple writers touched same file | Halt and register collision |
| test_failure | Tests, lint, or build failed | Queue fix |
| dependency_error | Missing or incompatible dependency | Queue environment fix |
| context_drift | Agent used stale or wrong context | Halt and refresh project state |
| scope_breach | Agent acted outside allowed files | Incident review |
| secret_exposure | Secret appeared in output/log/file | Critical incident |
| loop_behavior | Agent/tool retry spiral | Quarantine task |
| model_misroute | Wrong model/agent used | Update routing rule |
| playbook_gap | Missing governance rule | Add learning/playbook update |
| permission_error | Access denied or missing auth | Queue setup fix |
| git_state_error | Dirty tree, merge conflict, branch mismatch | Halt and inspect Git state |

---

## 10. Collision Control

When two IDEs, terminals, agents, or tools attempt to write the same file, the Harness must:

1. Stop further writes to the affected file.
2. Snapshot known versions if available.
3. Register a collision in `COLLISION_REGISTER.md`.
4. Assign one resolver.
5. Prevent original writers from auto-resolving unless authorized.
6. Record the final decision and learning.

---

## 11. Acceptance Criteria

The subsystem is accepted when:

- [ ] `HARNESS_EVENT_SCHEMA.json` validates example events.
- [ ] `log_harness_event.py` can append redacted events.
- [ ] `validate_event_log.py` can detect malformed lines.
- [ ] `detect_file_collisions.py` can compare active writers against file paths.
- [ ] `summarize_error_patterns.py` can group repeated signatures.
- [ ] Critical events are clearly routed to incident handling.
- [ ] File collisions are not silently ignored.
- [ ] Learnings link back to evidence.
- [ ] Agents have a usage guide and mission packets.

---

## 12. Implementation Phases

### Phase 1: Static Governance

Create docs, schema, logs, and templates.

### Phase 2: CLI Logging

Add script-based event capture, redaction, validation, and summarization.

### Phase 3: IDE + Agent Integration

Add VS Code/Cursor task wrappers, Claude/Codex handoffs, and GO-mode logging instructions.

### Phase 4: Automated Pattern Learning

Cluster repeated failures, suggest fix patterns, and create queue items.

### Phase 5: Governance Hardening

Add CI validation, collision locks, incident review gates, and dashboard reporting.

---

## 13. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---:|---:|---|
| Logging noise becomes overwhelming | Medium | Medium | Severity thresholds and summary reports |
| Secrets accidentally logged | Medium | Critical | Redaction script and critical incident route |
| Agents ignore logging | Medium | High | Add logging to playbooks and mission packets |
| Collision detection too weak | High | Medium | Start with active writer registry, then add Git integration |
| Humans stop reading logs | Medium | Medium | Maintain dashboard and pattern summaries |

---

## 14. Open Decisions

| Decision | Options | Recommendation |
|---|---|---|
| Event ID strategy | timestamp, UUID, monotonic counter | timestamp + short UUID |
| Storage format | JSON, JSONL, SQLite | JSONL first, SQLite later |
| Locking method | file lock, active writer registry, Git index | active writer registry first |
| Incident threshold | high+, critical only | critical always, high when mutation risk exists |
| Pattern summarizer | deterministic Python, local LLM, cloud LLM | deterministic first, LLM later |

---

## 15. Next Action

Install this bundle into the target repo and run:

```bash
python scripts/log_harness_event.py --source terminal --event-type info --severity info --category playbook_gap --message "Observability bundle initialized"
```
