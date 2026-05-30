# Daily Harness Audit Runbook

## Purpose

Run a lightweight daily audit to keep Chromatic Harness v2 healthy across Cursor, Claude Code, VS Code, CLI, routing, context, beads, and deployment workflows.

## Daily Command

```bash
python scripts/daily_harness_audit.py --root . --report
```

## Strict Mode

```bash
python scripts/daily_harness_audit.py --root . --report --strict
```

Use strict mode only after the repo has adopted all required files and wrappers.

## Recommended Daily Sequence

```bash
python scripts/new_session_bootstrap.py --root .
python scripts/context_trim_audit.py --root .
python scripts/daily_harness_audit.py --root . --report
bd ready
git status --short
```

## Optional Deployment Smoke

```powershell
powershell -NoProfile -File scripts/smoke_stack.ps1
```

## Review Outputs

```text
.agents/audits/latest_audit_summary.md
.agents/audits/latest_audit.json
.agents/audits/findings/open_findings.jsonl
```

## What to Do with Findings

| Finding | Action |
|---|---|
| Missing boot/context script | create or copy from approved pack |
| Instruction drift | update wrapper files |
| Missing VS Code task | update `.vscode/tasks.json` |
| Missing Cursor rule | add `.cursor/rules/harness-audit.mdc` |
| Missing beads command | install/configure `bd` |
| MCP audit unavailable | mark warning unless MCP-heavy work is planned |
| Tests fail | create bead and block execution if relevant |

## Daily Decision Rule

If audit status is red:

- do not launch new agent work
- do not run broad repo refactors
- compact/rebuild context first
- fix P0/P1 findings or create beads with owner and stop condition

If audit status is yellow:

- continue only with bounded tasks
- avoid broad context loading
- create beads for drift issues

If audit status is green:

- proceed normally
