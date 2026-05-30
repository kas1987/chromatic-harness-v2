# IDE / CLI Parity Policy

## Purpose

Ensure Cursor, Claude Code, VS Code, terminal shells, git hooks, and future agents use the same repo-owned operational workflow.

## Core Rule

Every environment may provide a wrapper, shortcut, command palette action, or slash command. No environment may own the policy.

The repo owns:

- bootstrapping
- context rebuild
- audit checks
- beads workflow
- routing policy
- session handoff rules

## Required Shared Commands

All environments should be able to run:

```bash
python scripts/new_session_bootstrap.py --root .
python scripts/context_trim_audit.py --root .
python scripts/context_rebuild.py --root . --mode hard
python scripts/daily_harness_audit.py --root . --report
```

## Environment Expectations

### Cursor

- Use `.cursor/rules/harness-audit.mdc`.
- Do not bulk-load old traces, JSONL logs, or archived sessions.
- Run MCP/context audits before long sessions.
- Use beads, not Cursor-only task lists.

### Claude Code

- `CLAUDE.md` should be a thin wrapper pointing to `AGENT_OPERATIONS.md` and repo scripts.
- Do not duplicate large governance sections unless generated and hash-verified.
- Read `.agents/context/BOOT_CONTEXT.md` after bootstrapping.

### VS Code

- `.vscode/tasks.json` should expose harness bootstrap, audit, context trim, and hard rebuild tasks.
- Extensions may wrap tasks but should not redefine policy.

### CLI

- Shell aliases may call the scripts.
- Shell aliases must not bypass beads or handoff protocol.

## Drift Conditions

A drift finding should be opened when:

- an IDE rule references obsolete commands
- an instruction file duplicates governance blocks that should be canonical
- VS Code tasks do not expose audit/bootstrap commands
- Claude/Cursor instructions contradict `AGENT_OPERATIONS.md`
- scripts are missing from one environment but referenced by another

## Severity

| Severity | Meaning | Action |
|---|---|---|
| P0 | unsafe/destructive or secrets risk | stop and fix |
| P1 | agent may execute with wrong context | fix before agent dispatch |
| P2 | parity/documentation drift | schedule fix |
| P3 | polish or future improvement | backlog |
