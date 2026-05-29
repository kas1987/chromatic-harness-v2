# Chromatic Harness v2 Manifest

## Mission

Chromatic Harness v2 turns user intent into governed missions, executes them through agents, observes them through Magnets, scores them through CMP, and converts findings into Beads, PDRs, and next actions through a reusable frontend console.

## Operating Stack

| Layer | Purpose |
|---|---|
| CMP | Governance, mission rules, confidence gates, permissions, tool budgets |
| Magnets | Deterministic observability, scoring, anomaly detection, evidence capture |
| Runtime | LangGraph, ADK, or custom runners executing bounded workflows |
| MCP | Tool, file, repo, database, browser, and API access |
| Beads | Structured backlog/action/task intake objects |
| Agent Lead | Final synthesis, review, reporting, and next-action planning |
| Console | Visibility, alerts, review swarm, quick action dispatch |
| Sandbox Lab | Safe testing for new agents and frameworks |

## Source of Truth Rule

This manifest and the protocol specs are authoritative. Agent docs, frontend docs, runtime scripts, and prompts must defer to these files rather than duplicating policy.

## Session Continuity

All harness agents (Claude, Pi, Codex, and registered runtimes) follow [12_HANDOFFS/SESSION_COMPACT.md](../12_HANDOFFS/SESSION_COMPACT.md) for context compaction and handoff. Chat history is not authoritative; beads, git, and handoff files are.

## Pre-Session Tool Inventory

Documented baseline of native tools, MCP servers, and CRG resources: [docs/PRE_SESSION_AND_TOOLS.md](../docs/PRE_SESSION_AND_TOOLS.md). Regenerate before changing tool exposure: `python scripts/generate_pre_session_inventory.py`.
