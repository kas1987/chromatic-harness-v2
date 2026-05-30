# Agent Instructions

> **START HERE:** [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md) — mandatory checklist for Claude, Pi, Codex, and all harness agents.

Agents must not infer owner intent from chat context. Execute from explicit artifacts: beads, mission packets, PDRs, playbooks, governance policies, routing config, tests, and handoffs.

**Canonical map:** [00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md](00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md)  
**Context tiers:** [docs/governance/PRE_SESSION_CONTEXT_POLICY.md](docs/governance/PRE_SESSION_CONTEXT_POLICY.md)  
**Bead types:** [docs/BEADS_OBJECT_MODEL.md](docs/BEADS_OBJECT_MODEL.md)

## Mandatory rules

- Use `bd` for all task tracking — not TodoWrite, TaskCreate, or markdown TODO lists.
- Run `bd prime` and `bd ready` before selecting work.
- Read `.agents/handoffs/latest.json` if present.
- Check git branch and status before edits.
- Compact and hand off at phase boundaries or session end — see [12_HANDOFFS/SESSION_COMPACT.md](12_HANDOFFS/SESSION_COMPACT.md).

## Non-interactive shell

Use non-interactive flags (`cp -f`, `mv -f`, `rm -f`, `ssh -o BatchMode=yes`, `scp -o BatchMode=yes`) so commands never hang on prompts.

## Beads (quick reference)

```bash
bd ready
bd show <id>
bd update <id> --claim
bd close <id>
```

Full workflow, session completion, and `bd dolt push`: [AGENT_OPERATIONS.md](AGENT_OPERATIONS.md).

**Git autonomy:** commit/push when [docs/governance/GIT_AUTONOMY_POLICY.md](docs/governance/GIT_AUTONOMY_POLICY.md) gates pass — run `python scripts/workflow_git.py plan` first; do not wait for a separate user “please commit” in this repo.
