# Claude Workflow Governance

## Default Mode

All workflows operate in bounded mode unless explicitly invoked as DEEP.

## Forbidden by Default

- Reading all project transcripts
- Globbing `~/.claude/projects/**/*.jsonl`
- Reading every `SKILL.md`
- Running full skill audits
- Passing full prior agent output to later agents
- Returning giant tables or raw logs into context
- Dispatching subagents without a budget packet

## Required Before Any Agent Call

Each workflow phase must define:

- Objective
- Allowed files
- Forbidden files
- Max tool calls
- Max files read
- Max output tokens
- Stop condition
- Compressed handoff format

## Context Passing Rule

Agents must pass compressed handoffs, not full transcripts.

Required handoff format:

```json
{
  "objective": "",
  "decision": "",
  "evidence_refs": [],
  "files_touched": [],
  "risks": [],
  "blockers": [],
  "next_action": "",
  "confidence": 0,
  "budget_used": {
    "tool_calls": 0,
    "files_read": 0,
    "approx_tokens": 0
  }
}
```

## Transcript Access Rule

Access to `~/.claude/projects/**/*.jsonl` requires explicit DEEP_AUDIT approval.

Default allowed transcript access:

- 0 files for normal workflows
- max 3 sampled files for cost audit
- indexed summaries preferred

## Stop Conditions

Stop immediately if:

- tool calls exceed budget
- context estimate exceeds budget
- same directory is scanned twice
- agent attempts full-history mining
- output exceeds phase limit
- task scope expands without approval
