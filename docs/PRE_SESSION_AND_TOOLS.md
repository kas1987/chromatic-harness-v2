# Pre-Session Tools, Resources, and MCP Inventory

> **Generated:** `2026-06-16T20:12:22.116491+00:00`  
> **Regenerate:** `python scripts/generate_pre_session_inventory.py`  
> **MCP path scanned:** `C:\Users\kas41\.cursor\projects\c-Users-kas41-chromatic-harness-v2\mcps`

Baseline documentation before changing tool exposure, MCP plugins, or CRG policy.
See also: [12_HANDOFFS/SESSION_COMPACT.md](../12_HANDOFFS/SESSION_COMPACT.md)
**Lean Cursor context:** [docs/CURSOR_CONTEXT_HYGIENE.md](../docs/CURSOR_CONTEXT_HYGIENE.md) — `python scripts/audit_mcp_context.py`

---

## Summary

| Category | Count |
| --- | --- |
| Native VS Code tools | 16 |
| Subagent types | 5 |
| MCP servers (registered) | 4 |
| MCP tools (descriptors) | 36 |
| CRG manifest resources | 15 |

---

## Three layers (do not confuse)

| Layer | What it is | Loaded when |
|-------|------------|-------------|
| **Instruction context** | Rules, AGENTS.md, tool schemas, skill catalog summaries | Every turn |
| **Invoked tools** | Shell, Read, MCP calls, skill file reads | On use |
| **Harness CRG** | Router manifest of allowed pre-context resources | Per task via ContextGate |

---

## Native VS Code tools

| Tool | Purpose |
| --- | --- |
| run_in_terminal | Run shell commands in a persistent PowerShell terminal |
| read_file / list_dir | Read files and inspect workspace structure |
| file_search / grep_search / semantic_search | Find files and code quickly |
| apply_patch / create_file | Edit and create files safely |
| get_errors | Read compiler/linter diagnostics |
| run_task / create_and_run_task | Run and define VS Code tasks |
| runSubagent | Delegate exploration or specialized workflows |
| vscode_askQuestions | Collect structured user input |
| vscode_listCodeUsages / vscode_renameSymbol | Symbol-aware code navigation and rename |
| copilot_getNotebookSummary / edit_notebook_file | Notebook-aware editing workflow |
| open_browser_page / read_page | Browser automation and state inspection |
| fetch_webpage | Fetch and summarize web pages |
| memory | Persist user/session/repo notes |
| get_changed_files | Inspect git staged/unstaged changes |
| testFailure | Retrieve recent test failure details |
| task_complete | Mark task completion for the session |

### Subagents (`Task` tool)

`Explore`, `Context Architect`, `modernize`, `planning-coordinator`, `execution-coordinator`

**Repo rule:** Use `bd` for task tracking — not `TodoWrite`.

---

## MCP servers (workspace descriptors)

### `cursor-app-control` (cursor-app-control) — 5 tools

`create_project`, `move_agent_to_cloned_root`, `move_agent_to_root`, `open_automation`, `rename_chat`

### `cursor-ide-browser` (cursor-ide-browser) — 16 tools

**Categories:** `browser_cdp`, `browser_click`, `browser_drag`, `browser_fill`, `browser_get_bounding_box`, `browser_highlight`, `browser_lock`, `browser_mouse_click_xy`, … (+8 more)

<details><summary>Full tool list</summary>

`browser_cdp`, `browser_click`, `browser_drag`, `browser_fill`, `browser_get_bounding_box`, `browser_highlight`, `browser_lock`, `browser_mouse_click_xy`, `browser_navigate`, `browser_press_key`, `browser_scroll`, `browser_select_option`, `browser_snapshot`, `browser_tabs`, `browser_take_screenshot`, `browser_type`

</details>

### `user-codegraph` (codegraph) — 10 tools

`codegraph_callees`, `codegraph_callers`, `codegraph_context`, `codegraph_explore`, `codegraph_files`, `codegraph_impact`, `codegraph_node`, `codegraph_search`, `codegraph_status`, `codegraph_trace`

### `user-review-daemon` (review-daemon) — 5 tools

`review_enqueue`, `review_package`, `review_run`, `review_ship`, `review_status`

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

## CRG -> VS Code tool mapping (baseline)

| CRG resource | VS Code surface | Notes |
| --- | --- | --- |
| read | read_file | Native |
| write | apply_patch / create_file | Native |
| edit | apply_patch | Native |
| bash | run_in_terminal | Native |
| audit | skill Read + runSubagent | Pull |
| test | run_task / run_in_terminal | Native |
| security | security tools (activated MCP) + scripts | Pull / MCP |
| council | runSubagent | Native |
| github_read | github_repo / github_text_search | MCP (auth may be required) |
| github_write | git commands via run_in_terminal | Controlled |
| web_search | fetch_webpage | Native |
| shell_execute | run_in_terminal | Native |
| secrets_read | Blocked by policy | Critical - gate |
| browser | open_browser_page + page interaction tools | Native |
| codex_team | runSubagent | Native |

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
