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

## Token Governance Closed Loop

```bash
python scripts/token_governance_closed_loop.py --enqueue-suggestions --drain-intake
```

This command ensures token usage controls are logged, analyzed, validated, and translated into intake suggestions that can become beads via `auto_intake`.

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
07_LOGS_AND_AUDIT/token_governance/latest.json
07_LOGS_AND_AUDIT/token_governance/latest.md
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

## Bead Hygiene Threshold Governance

The strict audit supports a temporary downgrade gate for bead hygiene red findings:

```bash
python scripts/daily_harness_audit.py --root . --report --strict --bead-hygiene-active-duplicate-threshold <N>
```

Environment-based automation override:

```bash
CHROMATIC_BEAD_HYGIENE_ACTIVE_DUPLICATE_THRESHOLD=<N>
```

Policy for threshold changes:

- Default threshold is `0`.
- Only raise threshold for active remediation windows with a linked bead and owner.
- Every threshold increase must include:
	- reason and expected end date
	- current active duplicate count
	- target duplicate count before reset
- Reset threshold to `0` when remediation target is reached.
- Do not use threshold changes to suppress unrelated P0/P1 findings.

Operator accountability checklist:

- Record threshold decisions in `.agents/audits/latest_audit_summary.md` notes or linked bead.
- Regenerate remediation commands via `python scripts/bead_hygiene_remediation_commands.py --write` after each cleanup wave.
- Re-run strict audit after cleanup and confirm finding code shifts from `bead_hygiene_red` to either `bead_hygiene_red_below_threshold` (temporary) or cleared.
