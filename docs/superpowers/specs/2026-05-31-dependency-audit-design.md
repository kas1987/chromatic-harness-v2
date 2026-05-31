# dependency-audit Plugin — Design Spec

**Date:** 2026-05-31  
**Status:** Approved  
**Install target:** `~/.claude/plugins/local/dependency-audit/`

---

## Purpose

A global Claude Code plugin that audits any repo's declared vs actual dependencies across Python, Node/TypeScript, and shell — and reports MCP tool usage frequency, coverage gaps, and cost from harness logs. Invoked as `/dependency-audit`.

---

## File Layout

```
~/.claude/plugins/local/dependency-audit/
├── .claude-plugin/
│   └── plugin.json
└── skills/
    └── dependency-audit/
        ├── SKILL.md
        ├── scripts/
        │   ├── run_audit.py        # entrypoint: arg parsing, orchestrates scanners
        │   ├── audit_python.py     # requirements*.txt / pyproject.toml vs ast-parsed .py
        │   ├── audit_node.py       # package.json vs import/require in .ts/.js
        │   ├── audit_shell.py      # .sh files → external tool calls
        │   ├── audit_mcp.py        # 07_LOGS_AND_AUDIT/ JSONL → freq/coverage/cost
        │   └── render.py           # JSON → terminal tables + written report file
        └── references/
            └── log-schema.md       # expected JSONL shapes for MCP log parsing
```

`installed_plugins.json` gets a new `dependency-audit@local` entry.

---

## SKILL.md Metadata

| Field | Value |
|---|---|
| name | `dependency-audit` |
| model | `haiku` |
| permissions allowed | `Read, Glob, Grep, Bash, Write` |
| permissions forbidden | `Edit, Agent, Skill, WebFetch, WebSearch` |
| trigger phrases | `dependency-audit`, `dep audit`, `audit deps`, `audit dependencies`, `show me deps`, `what deps are we using` |

---

## Invocation

```
/dependency-audit                    # scan $PWD
/dependency-audit --path /some/repo  # scan specific path
/dependency-audit --python-only      # skip node/shell/mcp sections
/dependency-audit --mcp-only         # just MCP intelligence report
```

---

## Execution Sequence

1. Skill parses args, sets `TARGET_PATH` (default: `$PWD`)
2. Invokes `python3 <skill_dir>/scripts/run_audit.py --path <TARGET_PATH> [--flags]`
3. `run_audit.py` calls each enabled scanner; each emits a JSON blob
4. `render.py` consumes all scanner JSON → terminal summary + full report file
5. Report written to `<TARGET_PATH>/07_LOGS_AND_AUDIT/dep-audit/YYYY-MM-DD-HH.md`  
   Fallback (no `07_LOGS_AND_AUDIT/`): `<TARGET_PATH>/dep-audit-report.md`
6. Terminal prints summary + final file path

---

## Scanners

### audit_python.py
- **Declared:** parse `requirements.txt`, `requirements-*.txt`, `pyproject.toml` (`[tool.poetry.dependencies]` + `[project.dependencies]`)
- **Actual:** `ast.parse()` every `.py` file (excluding `.venv/`, `node_modules/`, `.worktrees/`), collect all `import X` and `from X import Y` top-level module names
- **Reports:** unused declared packages, undeclared imports (present in source but absent from manifest)

### audit_node.py
- **Declared:** parse `package.json` `dependencies` + `devDependencies` in `TARGET_PATH` (and subdirs up to 2 levels, excluding `node_modules/`)
- **Actual:** regex-scan `.ts`, `.js`, `.tsx`, `.jsx` files for `import ... from '...'` and `require('...')`, extract bare package names
- **Reports:** unused declared packages, undeclared bare imports

### audit_shell.py
- **Declared:** n/a (no manifest for shell deps)
- **Actual:** scan all `.sh` files for external commands (words following pipes, `&&`, `;`, line starts — excluding builtins and variables)
- **Reports:** full list of external tools called, flag any not resolvable via `command -v`

### audit_mcp.py
- **Registered:** read `~/.claude.json` (or `.claude.json` in `TARGET_PATH`) — extract all `mcpServers` tool names
- **Actual usage:** read `07_LOGS_AND_AUDIT/` JSONL files — specifically:
  - `budget/ledger.jsonl` — tool call costs
  - `token_governance/history.jsonl` — per-tool token usage
  - `AGENT_RUN_LOG.jsonl` — tool call frequency
- **Reports:**
  - **Frequency:** top N tools by call count (last 30 days)
  - **Coverage:** registered tools never called (dead registrations), with last-called date where known
  - **Cost:** per-tool token cost rollup, per-skill cost rollup

---

## Terminal Output Format

```
═══ DEPENDENCY AUDIT — <repo-name> ════════════════════════════════
<timestamp>  |  Full report: <path>

── PYTHON ──────────────────────────────────────────────────────────
  Declared: N packages  |  Imported: N packages
  ✗ Unused declared:   <list>
  ✗ Undeclared imports: <list>

── NODE / TYPESCRIPT ────────────────────────────────────────────────
  Declared: N packages  |  Imported: N packages
  ✗ Unused declared:   <list>
  ✓ No undeclared imports   (or list)

── SHELL SCRIPTS ────────────────────────────────────────────────────
  .sh files scanned: N
  External tools: <list>
  ⚠ Not found in PATH: <list>

── MCP TOOLS ────────────────────────────────────────────────────────
  Registered: N  |  Called (30d): N  |  Dead: N
  Top 5 by calls:  <tool(count) list>
  Top 5 by cost:   <tool($cost) list>
  Dead registrations: <list>
════════════════════════════════════════════════════════════════════
```

---

## Full Report File

The written `.md` report extends the terminal summary with:
- Per-file import breakdowns (Python + Node)
- Full dead-tool list with last-called date
- Per-skill cost rollup table
- Raw package ↔ import cross-reference table
- Shell external tool → file mapping

---

## Exclusion Defaults

Scanners skip these paths by default:
- `.venv/`, `venv/`, `__pycache__/`
- `node_modules/`
- `.worktrees/`
- `.git/`
- `dist/`, `build/`

---

## Error Handling

- If `07_LOGS_AND_AUDIT/` is absent, `audit_mcp.py` emits a warning and skips (does not fail)
- If no `requirements.txt` / `package.json` found, scanner emits `"no manifest found"` and skips
- If Python < 3.8, `run_audit.py` exits with a clear error message
- All scanners return `{"error": "<msg>"}` on failure so `render.py` can surface gracefully
