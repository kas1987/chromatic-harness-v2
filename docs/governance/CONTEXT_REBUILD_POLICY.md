# Context Rebuild Policy

## Purpose

This policy defines when and how Chromatic Harness v2 agents should trim, compact, or rebuild context.

The goal is to prevent agents from operating inside bloated or stale context windows while preserving durable state in beads, handoffs, git, and approved governance files.

---

## Core Principle

Agents do not use long chat history as the system of record.

Agents use:

1. Beads for work state.
2. Handoffs for session continuity.
3. Git for repo truth.
4. Governance docs for policy.
5. Boot context for the next bounded session.

---

## Context Health Levels

| Level | Context Usage | Status | Behavior |
|---|---:|---|---|
| Green | 0-40% | Healthy | Normal work |
| Yellow | 40-60% | Watch | Avoid unnecessary broad reads |
| Orange | 60-75% | Risk | Compact soon; no broad repo/doc loading |
| Red | 75%+ | Stop | Rebuild before new planning or execution |

---

## Red-Zone Rule

At red context, agents must stop expanding context.

Forbidden in red-zone:

- New architecture planning.
- New agent dispatch.
- Repo-wide search.
- Bulk log reads.
- Importing large docs.
- Continuing exploratory discussion.

Required in red-zone:

1. Generate or update session handoff.
2. Run context audit.
3. Generate context rebuild manifest.
4. Generate `BOOT_CONTEXT.md`.
5. Restart or continue from the boot context only.

---

## Always Load at Session Start

The following are allowed as P0 boot context:

```text
.agents/handoffs/latest.json
Referenced active handoff file
Selected active bead details
Git branch/status summary
.agents/context/BOOT_CONTEXT.md when present
```

---

## Load Only If Relevant

The following require task relevance:

```text
AGENT_OPERATIONS.md
04_PLAYBOOKS/*.md
docs/governance/*.md
docs/workflows/*.md
09_DEPLOYMENT/config/routing/*.yaml
DEPLOYMENT_GUIDE.md
GOVERNANCE_AND_ROUTING_ARCHITECTURE.md
```

---

## Never Auto-Load

The following should never be loaded automatically:

```text
~/.claude/projects/**/*.jsonl
07_LOGS_AND_AUDIT/**/*.jsonl
traces/**/*.jsonl
old handoff chains
archive folders
entire docs folder
entire repo tree
screenshots unless image analysis is the mission
```

---

## Operating Modes

### Soft Compact

Use when context is yellow or orange.

Purpose:

- Reduce drift.
- Record current state.
- Keep session alive.

### Hard Compact

Use when context is red or before a major new mission.

Purpose:

- Create clean boot context.
- Block stale context.
- Re-enter from minimal state.

### Nuclear Rebuild

Use when prior context is unreliable.

Purpose:

- Preserve only durable state.
- Quarantine old state.
- Require explicit human approval for any cleanup.

---

## Agent Requirements

Before claiming a task, an agent should know:

- Current branch.
- Active bead or mission.
- Relevant handoff.
- Allowed docs.
- Forbidden auto-loads.
- Routing context when model selection matters.
- Stop condition.

---

## Review Gate

Before continuing after rebuild, verify:

- `BOOT_CONTEXT.md` exists.
- Active mission is clear.
- Active bead is clear or intentionally absent.
- No bulk logs were loaded.
- Required governance docs are linked, not copied.
- Next action is bounded.

---

## Law

If the agent cannot explain why a document is needed for the active mission, it should not load that document.
