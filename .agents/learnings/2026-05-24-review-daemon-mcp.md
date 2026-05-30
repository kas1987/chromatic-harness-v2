---
id: research-2026-05-24-review-daemon-mcp
type: research
date: 2026-05-24
---

# Research: In-Review Layer — Live Daemon MCP Server

**Backend:** inline  
**Scope:** MCP server patterns, LLM router integration, governance pipeline design

## Summary

The existing `live-director` MCP establishes the canonical TypeScript pattern for Claude Code MCP servers: `@modelcontextprotocol/sdk`, StdioServerTransport, tool manifest array, individual tool files per `src/tools/`. A new `review-daemon` MCP will follow this exact pattern, adding a persistent queue-based In Review layer that routes mechanical checks to local tiers (0-2) and judgment reviews to cloud tiers (3-4), then executes a two-layer governance pipeline (local commit → GitHub PR).

## Key Files

| File | Purpose |
|------|---------|
| `~/.claude/director-mcp/src/index.ts` | Canonical MCP server entry point pattern |
| `~/.claude/director-mcp/src/tools/*.ts` | Per-tool module pattern |
| `~/.claude/director-mcp/package.json` | Build config: ESM, tsx, tsc |
| `~/.claude/.claude.json` | MCP registration: stdio, node, dist/index.js |
| `~/.claude/hooks/model-router.sh` | LLM tier routing hook (pattern to replicate) |
| `~/.claude/config/router-patterns.json` | Tier assignment by task pattern |
| `~/.claude/.agents/router/session-health.json` | State file pattern for daemon output |

## Findings

### MCP Framework (TypeScript)
- SDK: `@modelcontextprotocol/sdk` v1.0.0
- Transport: StdioServerTransport (Claude Code reads stdout, writes stdin)
- Server pattern: `new Server({name, version}, {capabilities: {tools: {}}})` 
- Tool registration: `server.setRequestHandler(ListToolsRequestSchema, ...)` returns `{tools: TOOLS}`
- Tool dispatch: `server.setRequestHandler(CallToolRequestSchema, ...)` switches on tool name
- Each tool returns `{content: [{type: "text", text: JSON.stringify(result)}]}`

### Registration in .claude.json
```json
"review-daemon": {
  "type": "stdio",
  "command": "node",
  "args": ["C:\Users\kas41\.claude\review-daemon\dist\index.js"]
}
```

### LLM Router Tier Assignment for Review Tasks
| Check Type | Tier | Provider | Model |
|------------|------|----------|-------|
| Lint, format, syntax | T0 | Ollama | llama3.2:3b |
| Schema, boilerplate conformance | T1 | Featherless | Hermes-8B |
| Single-file style/pattern | T2 | Featherless/mid | — |
| Multi-file design + harness alignment | T3 | Claude | Haiku |
| Session goal alignment + final judgment | T4 | Claude | Sonnet |

### State Model
Queue file: `~/.claude/.agents/review/queue.jsonl`  
Each entry: `{id, files[], goal, status: queued|reviewing|approved|shipped, tier_results{}, created_at, updated_at}`

### Two-Layer Governance
1. **Local layer:** review-daemon runs checks → local commit to session branch → all approved
2. **GitHub layer:** `gh pr create` with review evidence in body → CI / human as final gate

### Constraints (from harness)
- Constraint #2: Never push to main — always session branch + PR
- Constraint #6: Tier 0-2 work stays local — mechanical review via Ollama, not Claude API
- Constraint #5: PR merge (if auto) is T4 — requires confirmation unless pre-approved

## Recommendations

1. Build TypeScript MCP matching `director-mcp` structure exactly
2. State file at `~/.claude/.agents/review/` (matches `.agents/router/` pattern)  
3. Tier routing: call `model-router.sh` patterns via direct shell commands (not re-importing the hook)
4. Mechanical reviewer: shell-based (ruff, eslint, bash -n, jq) — no LLM at T0-T1
5. Judgment reviewer: Anthropic SDK calls with tier-appropriate model
6. `review_ship` requires user confirmation for PR merge (T4 gate)
7. SessionStart hook to auto-start daemon (follow `multica-startup.sh` pattern)

