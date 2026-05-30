# Hook Audit Report

Repo: `C:\Users\kas41\chromatic-harness-v2`

## Executive summary

| Surface | Hook count | Notes |
|---------|------------|-------|
| claude_code | 19 | |
| cursor | 1 | |
| repo_script | 4 | |

## Findings

### MED: Many SessionStart hooks

6 SessionStart hooks ù additive latency at every session open.

### LOW: Chromatic Task Scheduler tasks not installed

Run scripts/install_automation_tasks.ps1 for hands-off intake/boot.

## Claude Code + Cursor hook registry

| Platform | Source | Event | Matcher | Timeout | Command |
|----------|--------|-------|---------|---------|---------|
| claude_code | `settings.json` | SessionStart | (all) | 15 | `~/.claude/bin/ao.sh extract 2>/dev/null \|\| true` |
| claude_code | `settings.json` | SessionStart | (all) | 5 | `python3 ~/.claude/skills/prompt-db/scripts/prompt-db.py inject --n 10 2>/dev/nul` |
| claude_code | `settings.json` | SessionStart | (all) | 5 | `bash ~/.claude/hooks/ollama-liveness.sh 2>/dev/null \|\| true` |
| claude_code | `settings.json` | SessionStart | (all) | 10 | `bash ~/.claude/hooks/session-health.sh 2>/dev/null \|\| true` |
| claude_code | `settings.json` | SessionEnd | (all) | 15 | `~/.claude/bin/ao.sh forge transcript --last-session --queue --quiet >/dev/null 2` |
| claude_code | `settings.json` | Stop | (all) | 30 | `~/.claude/hooks/usage-tracker.sh` |
| claude_code | `settings.json` | Stop | (all) | 15 | `~/.claude/bin/ao.sh flywheel close-loop --quiet 2>/dev/null \|\| true` |
| claude_code | `settings.json` | Stop | (all) | 10 | `bash ~/.claude/hooks/context-guard.sh` |
| claude_code | `settings.json` | UserPromptSubmit | (all) | 10 | `bash ~/.claude/hooks/context-guard.sh UserPromptSubmit` |
| claude_code | `settings.json` | PostToolUse | Write|Edit|NotebookEdit | 10 | `~/.claude/hooks/post-file-write.sh` |
| claude_code | `settings.json` | PostToolUse | (all) | 5 | `bash ~/.claude/hooks/response-size-guard.sh` |
| claude_code | `settings.json` | PreToolUse | Bash | 30 | `~/.claude/hooks/pre-commit.sh` |
| claude_code | `settings.json` | PreToolUse | Bash | 5 | `python3 ~/.claude/hooks/policy_gate.py \|\| true` |
| claude_code | `settings.json` | PreToolUse | (all) | 5 | `bash ~/.claude/hooks/injection-guard.sh` |
| claude_code | `settings.json` | Notification | (all) | 10 | `bash ~/.claude/hooks/notify-tts.sh` |
| claude_code | `settings.json` | PreCompact | (all) | 5 | `printf '%s' '{"systemMessage":"COMPACTION GUIDANCE: Do NOT include skill listing` |
| claude_code | `settings.json` | SessionStart | (all) | 120 | `python scripts/session_start.py` |
| claude_code | `settings.json` | PreCompact | (all) | 30 | `bd prime` |
| claude_code | `settings.json` | PreToolUse | Agent | 10 | `python 02_RUNTIME/router/gate.py` |
| cursor | `hooks.json` | sessionStart | (all) | 120 | `python .cursor/hooks/session_boot.py` |

## Repo workflows (slash commands, not lifecycle hooks)

- `README.md`
- `close-issue.js`
- `go.js`
- `hotfix.js`
- `qa.js`
- `ship.HEAVY.js.bak`
- `ship.js`

## Cursor always-on rules

- `.cursor/rules/context-hygiene.mdc`

## Windows Task Scheduler

- **ChromaticIntakeCycle**: not installed
- **ChromaticSmokeDaily**: not installed
- **ChromaticSessionBoot**: not installed
- **ChromaticSessionPreflight**: not installed

## CI guards (GitHub Actions)

- Agent operations: `scripts/check_agent_operations.py`
- Intake loop: `scripts/validate_intake_loop.py`
- MCP audit fixture: `scripts/audit_mcp_context.py --mcps-path tests/fixtures/mcp_minimal`

## IDE / CLI matrix

- **cursor**: sessionStart hook + alwaysApply rules (not full lifecycle)
- **claude_code**: Global ~/.claude/settings.json stacks with project .claude/settings.json
- **vscode**: No repo hooks ù relies on Cursor/Claude extensions
- **terminal**: No repo shell profile hooks ù use Task Scheduler or manual scripts

## Recommendations

1. **Claude Code:** Global `~/.claude/settings.json` and project `.claude/settings.json` **stack** ù every event runs both. Keep harness hooks only in the project file; avoid duplicating `gate.py` on `PreToolUse` / `Agent`.
2. **Cursor:** Only `sessionStart` is wired ù no `preToolUse` / `stop` hooks. Use `.cursor/rules/context-hygiene.mdc` for policy; add hooks only when you need hard gates.
3. **Terminal / hands-off:** Install Task Scheduler tasks: `install_automation_tasks.ps1` (boot, intake, smoke).
4. **Re-audit:** `python scripts/audit_hooks.py --markdown > docs/audit/HOOK_AUDIT_LATEST.md`
5. **Workflows:** `.claude/workflows/*.js` are slash-command prompts, not lifecycle hooks ù audit separately for token cost (`docs/AGENT_ANTIPATTERNS.md`).

## What is NOT a hook (but acts like one)

- `.cursor/rules/*.mdc` with `alwaysApply: true` ù injected rules every turn
- `AGENTS.md` / `CLAUDE.md` ù entry instructions
- GitHub Actions on push/PR ù CI guards, not IDE session hooks
- MCP server tools ù schema injection per turn when enabled in Cursor


