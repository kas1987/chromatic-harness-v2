# Pre-Session Tools, Resources, and MCP Inventory

> **Generated:** `2026-05-30T08:00:09.470575+00:00`  
> **Regenerate:** `python scripts/generate_pre_session_inventory.py`  
> **MCP path scanned:** `C:\Users\kas41\.cursor\projects\c-Users-kas41-chromatic-harness-v2\mcps`

Baseline documentation before changing tool exposure, MCP plugins, or CRG policy.
See also: [12_HANDOFFS/SESSION_COMPACT.md](../12_HANDOFFS/SESSION_COMPACT.md)
**Lean Cursor context:** [docs/CURSOR_CONTEXT_HYGIENE.md](../docs/CURSOR_CONTEXT_HYGIENE.md) — `python scripts/audit_mcp_context.py`

---

## Summary

| Category | Count |
| --- | --- |
| Native Cursor tools | 15 |
| Subagent types | 9 |
| MCP servers (registered) | 2 |
| MCP tools (descriptors) | 5 |
| CRG manifest resources | 15 |

---

## Three layers (do not confuse)

| Layer | What it is | Loaded when |
|-------|------------|-------------|
| **Instruction context** | Rules, AGENTS.md, tool schemas, skill catalog summaries | Every turn |
| **Invoked tools** | Shell, Read, MCP calls, skill file reads | On use |
| **Harness CRG** | Router manifest of allowed pre-context resources | Per task via ContextGate |

---

## Native Cursor tools

| Tool | Purpose |
| --- | --- |
| Shell | Run terminal commands (git, bd, pytest, docker) |
| Read | Read files including images |
| Write / StrReplace / Delete | Create and edit files |
| Grep | Ripgrep search |
| Glob | Find files by pattern |
| WebSearch / WebFetch | Web lookup when enabled |
| GenerateImage | Image generation when explicitly requested |
| ReadLints | IDE linter diagnostics |
| EditNotebook | Jupyter cell edits |
| CallMcpTool | Invoke MCP server tools |
| FetchMcpResource | Read MCP resources |
| Task | Spawn subagents (explore, shell, ci-investigator, etc.) |
| SwitchMode | Plan vs agent mode |
| AskQuestion | Structured user multiple-choice |
| Await | Poll background shells |

### Subagents (`Task` tool)

`generalPurpose`, `explore`, `shell`, `cursor-guide`, `ci-investigator`, `best-of-n-runner`, `granola-engineer`, `devsecops`, `investigator`

**Repo rule:** Use `bd` for task tracking — not `TodoWrite`.

---

## MCP servers (Cursor workspace)

### `cursor-app-control` (cursor-app-control) — 5 tools

`create_project`, `move_agent_to_cloned_root`, `move_agent_to_root`, `open_automation`, `rename_chat`

### `cursor-backend-control` (cursor-backend-control) — 0 tools

*Registered but no tool descriptors — likely needs authentication or plugin not connected.*

---

## Harness CRG manifest (Context Resource Governance)

What the router may allow into pre-context for Pi / governed Claude sessions.
Filtered by `09_DEPLOYMENT/config/routing/context-policy.yaml`.

| ID | Type | Tokens | Risk | Description |
| --- | --- | --- | --- | --- |
| audit | skill | 600 | low | Audit/refactor skills |
| bash | tool | 120 | high | Execute shell commands |
| browser | extension | 600 | medium | Browser automation |
| codex_team | agent | 900 | medium | Codex sub-agents |
| council | skill | 800 | low | Multi-model consensus |
| edit | tool | 100 | low | Precise file edits |
| github_read | mcp | 400 | low | GitHub read ops |
| github_write | mcp | 450 | medium | GitHub write ops |
| read | tool | 80 | low | Read file contents |
| secrets_read | mcp | 300 | critical | Secret manager access |
| security | skill | 700 | medium | Security scanning |
| shell_execute | mcp | 500 | high | Remote shell execution |
| test | skill | 500 | low | Test generation and coverage |
| web_search | mcp | 350 | low | Web search/browse |
| write | tool | 80 | low | Write or overwrite files |

---

## Harness MCP families (spec — not yet implemented as servers)

From `01_PROTOCOLS/MCP/MCP_TOOL_MANIFEST.md`:

| Family | Purpose | Risk |
| --- | --- | --- |
| filesystem.read | Inspect files | Low |
| filesystem.patch | Patch scoped files | Medium |
| github.read | Issues, PRs, repo content | Low |
| github.write | Issues, branches, PRs | Medium |
| shell.execute | Run tests/scripts | High |
| database.read | Inspect state | Low |
| database.write | Update state | Medium |
| browser.search | Current research | Low |
| secrets.read | Secret access | Critical |
| deploy.production | Production deploy | Critical |

---

## CRG → Cursor mapping (baseline)

| CRG resource | Cursor surface | Notes |
| --- | --- | --- |
| read | Read | Native |
| write | Write | Native |
| edit | StrReplace | Native |
| bash | Shell | Native |
| audit | Skills (on-demand Read) | Pull |
| test | Skills (on-demand Read) | Pull |
| security | Skills + Opsera MCP | Pull / MCP |
| council | Skills (on-demand Read) | Pull |
| github_read | plugin-github-github | MCP (auth required) |
| github_write | plugin-github-github | MCP (auth required) |
| web_search | WebSearch / Playwright | Native / MCP |
| shell_execute | Shell / remote MCP | Native |
| secrets_read | Blocked by policy | Critical — gate |
| browser | plugin-playwright-playwright | MCP |
| codex_team | Task subagents | Native |

---

## Skills policy

Skills are **not** pre-loaded. The agent sees a catalog in instructions;
full content loads only when `Read` on a `SKILL.md` path.

Categories include: RPI/beads, package-ingest, security, Grafana, SDK, email, etc.

---

## Session start checklist

```bash
cat .agents/handoffs/latest.json    # if exists
bd prime && bd ready
git branch --show-current && git status --short
python scripts/generate_pre_session_inventory.py   # after MCP changes
```

---

## Change control (read before altering tools)

1. Run `python scripts/generate_pre_session_inventory.py` and commit the diff.
2. Update `09_DEPLOYMENT/config/routing/context-policy.yaml` if CRG rules change.
3. Update `02_RUNTIME/router/context_manifest.py` if resource IDs change.
4. Re-run `pytest tests/test_context_*.py` for CRG.
5. Note changes in beads / handoff for the next session.
