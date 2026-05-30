# PDR-CHV2-003: IDE/CLI Audit and Daily Monitoring System

## 0. Executive Summary

Chromatic Harness v2 needs one repo-owned audit system that checks whether Cursor, Claude Code, VS Code, CLI terminals, git hooks, beads, routing, context bootstrapping, MCP/tool hygiene, and deployment workflows are aligned.

The goal is not to make every environment identical. The goal is to ensure every environment calls the same repo-local scripts and obeys the same governance contracts.

## 1. Problem

Harness v2 is now operating across multiple execution surfaces:

- Cursor
- Claude Code
- VS Code
- local CLI terminals
- future Codex-style agents
- GitHub Actions
- local Windows and desktop GPU setups

Without an audit layer, each environment can drift:

- Cursor rules may say one thing.
- Claude instructions may say another.
- VS Code tasks may be stale.
- CLI users may skip bootstrapping.
- MCP plugins may bloat pre-session context.
- Beads may be ignored in favor of markdown TODOs.
- Routing/provider configs may silently break.

## 2. Goals

1. Create one daily audit command.
2. Detect IDE/CLI parity drift.
3. Detect instruction duplication and contradictions.
4. Verify pre-session context controls exist.
5. Verify beads are used as task source of truth.
6. Verify router/provider files and scripts exist.
7. Generate human-readable and machine-readable audit outputs.
8. Create backlog beads for remediation.
9. Support local-first operation with optional CI integration.

## 3. Non-Goals

- This PDR does not implement the full router.
- This PDR does not replace beads.
- This PDR does not enforce security scanning beyond lightweight repo checks.
- This PDR does not automatically edit governance files unless a future agent is assigned to do so.

## 4. Operating Principle

```text
Cursor can wrap the workflow.
Claude can wrap the workflow.
VS Code can wrap the workflow.
CLI can wrap the workflow.

But none of them own the workflow.

The repo owns the workflow.
```

## 5. Audit Layers

| Layer | Name | Purpose | Frequency |
|---:|---|---|---|
| L1 | Context Audit | Detect bloated pre-session context, duplicate docs, stale handoffs | Daily |
| L2 | Agent Instruction Audit | Check `AGENTS.md`, `CLAUDE.md`, Cursor rules, VS Code tasks alignment | Daily / Weekly |
| L3 | Beads Audit | Ensure work is tracked in `bd`, not TodoWrite/markdown TODOs | Daily |
| L4 | IDE Parity Audit | Verify Cursor, Claude, VS Code, CLI all call the same scripts | Weekly / CI |
| L5 | MCP/Tool Audit | Detect heavy MCP/tool-surface bloat | Daily |
| L6 | Routing Audit | Validate provider/routing configs and local/cloud fallbacks | Daily |
| L7 | Security Audit | Check obvious secrets, `.env`, risky scripts | Daily / CI |
| L8 | CI/Test Audit | Run unit tests, lint/build if configured | PR / Daily |
| L9 | Deployment Audit | Smoke API/frontend/docker health where available | Daily optional |
| L10 | Drift Audit | Detect duplicated/conflicting governance docs | Weekly |
| L11 | Knowledge Audit | Canon vs non-canon, stale source docs | Weekly |
| L12 | Recovery Audit | Confirm handoff, boot context, rebuild path works | Daily |

## 6. Proposed Files

```text
scripts/daily_harness_audit.py
scripts/audit_ide_parity.py
scripts/audit_instruction_drift.py
docs/governance/IDE_CLI_PARITY_POLICY.md
docs/governance/DAILY_AUDIT_RUNBOOK.md
.cursor/rules/harness-audit.mdc
.vscode/tasks.json
beads/IDE_CLI_AUDIT_BEADS.md
.github/workflows/harness-daily-audit.yml
```

## 7. Daily Audit Command

```bash
python scripts/daily_harness_audit.py --root . --report
```

The audit should attempt to run or inspect:

```bash
python scripts/new_session_bootstrap.py --root .
python scripts/context_trim_audit.py --root .
python scripts/generate_pre_session_inventory.py
python scripts/audit_mcp_context.py --profile harness_dev
python scripts/check_agent_operations.py
bd ready
git status --short
pytest tests/ -q
```

Missing optional commands are reported as warnings, not hard failures, unless strict mode is enabled.

## 8. Output Artifacts

```text
.agents/audits/latest_audit.json
.agents/audits/latest_audit_summary.md
.agents/audits/daily/YYYY-MM-DD_AUDIT_REPORT.md
.agents/audits/findings/open_findings.jsonl
```

## 9. Acceptance Criteria

- [ ] Daily audit command runs from repo root.
- [ ] Audit outputs JSON and Markdown reports.
- [ ] Cursor, Claude, VS Code, and CLI parity checks are represented.
- [ ] Instruction drift is detected.
- [ ] Missing core scripts are reported.
- [ ] Missing governance docs are reported.
- [ ] Beads follow-up backlog exists.
- [ ] CI workflow exists but does not require secrets.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Audit becomes too strict too early | Default to warning mode; use `--strict` only in mature repos |
| Daily audit becomes noisy | Severity levels and open findings JSONL |
| IDE wrappers drift anyway | Audit checks wrapper references to repo-owned scripts |
| Cursor still injects too much MCP context | Audit MCP profile and require lean mode before long sessions |
| Tests take too long | Use bounded timeout and allow optional skip |

## 11. Implementation Phases

### Phase 1 — Passive Audit

- Add scripts.
- Generate reports.
- Do not fail CI by default.

### Phase 2 — Strict Gates

- Enable `--strict` in CI for core governance files.
- Fail on missing boot/context scripts or missing instruction wrappers.

### Phase 3 — Daily Monitoring

- Add GitHub Actions schedule.
- Add Task Scheduler / cron examples.
- Convert audit findings into beads.

### Phase 4 — Dashboard Integration

- Surface audit status in the Harness console.
- Add trend history.
- Add open findings panel.

## 12. Recommended First Sprint

1. Copy this pack into repo root.
2. Run `python scripts/daily_harness_audit.py --root . --report`.
3. Review `.agents/audits/latest_audit_summary.md`.
4. Create beads from `beads/IDE_CLI_AUDIT_BEADS.md`.
5. Decide which warnings become strict gates.
