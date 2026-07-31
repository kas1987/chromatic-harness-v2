# Chromatic Harness v2 — Obsidian Index

A navigable index of the harness for [[Obsidian]]-style graph exploration.

## Core contracts

- [[../AGENTS.md|Agent Instructions]]
- [[../AGENT_OPERATIONS.md|Agent Operations]]
- [[REPO_BOUNDARY.md|Git Purpose & Boundary]]
- [[REPO_ARCHITECTURE.md|Architecture Maps]]
- [[../governance/PRE_SESSION_CONTEXT_POLICY.md|Context Policy]]
- [[../00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md|Execution Flow]]

## Layers

### Governance & source of truth
- [[../00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md]]
- [[../00_SOURCE_OF_TRUTH/canon_registry.yaml]]
- [[REPO_BOUNDARY.md]]
- [[../governance/GIT_AUTONOMY_POLICY.md]]

### Runtime
- [[../02_RUNTIME/README.md]] (if exists)
- [[../02_RUNTIME/router]]
- [[../02_RUNTIME/budget]]
- [[../02_RUNTIME/gen]]

### Agent skills
- [[../../.agents/skills/mattpocock/README.md|mattpocock skills]]
- [[../agents/issue-tracker.md|Issue tracker mapping]]
- [[../agents/triage-labels.md|Triage labels]]
- [[../agents/domain.md|Domain docs]]

### Observability & telemetry (runtime)
- `07_LOGS_AND_AUDIT/` — runtime only, see [[REPO_BOUNDARY.md]]
- `.agents/handoffs/` — per-session, see [[REPO_BOUNDARY.md]]
- `.codex/` — local plugin cache, see [[REPO_BOUNDARY.md]]

### Protocols
- [[../01_PROTOCOLS/MCP/MCP_TOOL_MANIFEST.md]]
- [[../01_STATE/README.md]] (if exists)
- [[../09_DEPLOYMENT/README.md]] (if exists)

## GraphQL-style domain schema

See [[HARNESS_SCHEMA.md]].
