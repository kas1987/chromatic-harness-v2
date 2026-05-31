---
name: 2026-05-03-nightly-extract
type: anti-pattern
confidence: 0.50
source_learnings: [2026-05-03-nightly-extract]
description: Nightly Extract — 2026-05-03
tags: []
---

# Nightly Extract — 2026-05-03

**Commits processed:** 10 (c6246f1, 3b791e9, d232959, 0c48612, 047ce8b, 094e807, c23a85d, cfc27c8, 0a46a87, 4455b6a)
**Signals found:** 11 (skipped 2 chore-only: fitness snapshot, prior nightly extract)

---

## Signal 1: Session Branching Workflow — start-session.sh + pre-push guard

**What:** `bin/start-session.sh` creates a `session/YYYY-MM-DD-[topic]` branch from latest master before work begins. Topic is slugified (sed/tr) to prevent invalid branch names. Uses `checkout -B` (idempotent — resets branch if it already exists). Auto-installs `hooks/pre-push.sh` symlink at `.git/hooks/pre-push` on first run. `hooks/pre-push.sh` blocks any direct push to `master` and redirects to `start-session.sh` + `gh pr create --draft`.

**Why:** Prevents accidental direct commits/pushes to master; ensures sessions always start from a clean, up-to-date base; enforces PR-based workflow.

**Reuse signal:** Any repo where the user wants to enforce a topic-branch + PR workflow. Template: `start-session.sh` + `hooks/pre-push.sh` symlinked into `.git/hooks/`.

**Source:** 3b791e9

---

## Signal 2: context-guard.sh — ACTIVE_TOKENS Calculation Bug Fixed

**What:** Original logic used `max(cache_read_input_tokens, input_tokens)` to estimate context pressure. Fixed to use `ACTIVE_TOKENS = INPUT_TOKENS` only.

**Why:** `cache_read_input_tokens` is already counted inside `input_tokens` per the Anthropic API spec — adding or maxing them double-counts. When cache is warm, both values are large and `max()` was returning an inflated but still *wrong* number. The real token footprint is simply `input_tokens`.

**Reuse signal:** Whenever computing context usage from Anthropic API response fields: `input_tokens` is the canonical total. Do not add or max with `cache_read_input_tokens`.

**Source:** d232959, 3b791e9

---

## Signal 3: python → python3 in Shell Scripts

**What:** `hooks/response-size-guard.sh` was calling bare `python`; changed to `python3` throughout.

**Why:** On many Linux/WSL systems `python` is absent or resolves to Python 2. `python3` is the safe, explicit invocation.

**Reuse signal:** All shell scripts in the repo that call Python inline should use `python3`. Audit any `python -c` or `python script.py` invocations.

**Source:** d232959, 3b791e9

---

## Signal 4: PreCompact Hook Timeout Added

**What:** The inline `printf` command in the `PreCompact` hook entry in `settings.json` gained `"timeout": 5`.

**Why:** Without a timeout, even a trivially fast `printf` can stall the compaction pipeline indefinitely if something goes wrong in the execution environment. Adding `timeout: 5` bounds the blast radius.

**Reuse signal:** Every hook `command` entry should have an explicit `timeout`. Even `printf`-only commands warrant a small value (5s) to prevent pipeline stalls.

**Source:** d232959

---

## Signal 5: MCP Duplicate Tool Name — enabledMcpjsonServers vs mcpServers

**What:** `wispr-flow` was listed in both `enabledMcpjsonServers` and (as `whisper-flow`) in `mcpServers`. Removed the `enabledMcpjsonServers` entry. `wispr-pack@npm` plugin removed for the same reason.

**Why:** Registering a server in both locations causes Claude Code to expose duplicate tool names, leading to ambiguous dispatch. The canonical registration for non-.mcp.json servers is `mcpServers`; `enabledMcpjsonServers` is for `.mcp.json`-defined servers only.

**Reuse signal:** When adding an MCP server, choose exactly one registration path: `mcpServers` (settings.json) OR `enabledMcpjsonServers` (.mcp.json). Never both.

**Source:** cfc27c8

---

## Signal 6: PreCompact Compaction Guidance Hook

**What:** `PreCompact` hook replaced a `ao.sh forge transcript` call with a `printf` that injects `additionalContext` into the compaction event. The guidance: skip skill listings, MCP tool listings, slash command descriptions (always re-injected from live context); preserve only decisions, code/files changed, errors + resolutions, current in-progress state, specific skills invoked and their output.

**Why:** Without guidance, Claude's compaction summaries bloat with tool/skill lists that are already available from system context, wasting the compacted context budget on redundant content.

**Reuse signal:** Any repo using context compaction should add a `PreCompact` hook with `additionalContext` specifying what to drop (stable/re-injectable content) vs. preserve (decisions, diffs, errors). Keep the hook fast (timeout: 5).

**Source:** cfc27c8, d232959

---

## Signal 7: Pre-commit Secrets Scrubbing for settings.json

**What:** `hooks/pre-commit.sh` calls `scrub-settings-secrets.py` before allowing a commit. The script strips any env key matching `TOKEN|SECRET|KEY|PASSWORD` from the staged `settings.json`. If the scrub fails, the commit aborts.

**Why:** `settings.json` is tracked and contains the `env` block. Adding credentials to the env block (e.g., `GITHUB_PERSONAL_ACCESS_TOKEN`) without a scrub guard would persist them permanently in git history.

**Reuse signal:** Any project where secrets might end up in tracked config files needs a pre-commit hook that strips or validates sensitive fields. The pattern: scrub staged file → overwrite staged version → continue commit.

**Source:** c23a85d

---

## Signal 8: context-guard.sh — Three-Stage Session File Lookup

**What:** New `hooks/context-guard.sh` introduced. To locate the current session's `.jsonl` token log, it tries three fallbacks in order: (1) look up `session_id` from stdin and `find` its file directly; (2) fuzzy-match `$(basename pwd)` against project dirs and take the most recently touched `.jsonl`; (3) `find` the most recently touched `.jsonl` across ALL project dirs.

**Why:** Claude Code session IDs are not always passed to hook stdin, and project dirs use encoded names. A graceful fallback chain ensures the guard works even in degraded conditions.

**Reuse signal:** Any hook that needs to read the current session file should implement this three-stage lookup rather than assuming a session ID will be available.

**Source:** 094e807

---

## Signal 9: response-size-guard.sh — PostToolUse Token Budget Guard

**What:** `hooks/response-size-guard.sh` (PostToolUse) measures tool response length, estimates tokens (`len / 4`), and emits both a `systemMessage` warning and `additionalContext` with tool-specific reduction tips (e.g., `depth/target` for `browser_snapshot`, `limit` for queries, `head_limit` for Grep/Bash) when the response exceeds 20k chars (~5k tokens).

**Why:** Oversized tool responses are a primary driver of context bloat. Giving the model actionable, tool-specific guidance at the moment of excess is more effective than a generic warning.

**Reuse signal:** PostToolUse size guards should include tool-specific remediation hints in `additionalContext`, not just a generic warning. Threshold: 20k chars / 5k tokens.

**Source:** 094e807

---

## Signal 10: notify-tts.sh — Windows System.Speech TTS Hook

**What:** `hooks/notify-tts.sh` reads `{"message": "..."}` from stdin and speaks it via `powershell.exe System.Speech.Synthesis.SpeechSynthesizer` in the background. Silent on empty/missing message. Zero error output redirected.

**Why:** Provides audio notification when Claude stops or sends a Notification event — useful when the terminal window is in the background.

**Reuse signal:** WSL/Windows users can add TTS notifications to any hook event by piping a JSON message to this script. Pattern: use `&` + `>/dev/null 2>&1` to fire-and-forget without blocking the hook.

**Source:** 094e807

---

## Signal 11: Scheduled Tasks as SKILL.md Files

**What:** `scheduled-tasks/weekly-skills-reflection/SKILL.md` and `scheduled-tasks/worktree-tooling-sweep/SKILL.md` — recurring operational tasks expressed as skill files with YAML frontmatter (`name`, `description`) and step-by-step instructions.

**Why:** Storing recurring tasks as skills makes them invokable via slash commands or skill dispatch without re-specifying the procedure each time. The worktree-tooling-sweep skill also documents a general pattern: use `git rev-parse --git-common-dir` → `TOOLS_ROOT` (not `--show-toplevel`) to find `node_modules` in scripts that may run inside a worktree.

**Reuse signal:** Recurring maintenance tasks (weekly reviews, sweeps, audits) should be stored as SKILL.md files in `scheduled-tasks/`. Worktree-safety pattern: always resolve `node_modules` from `git-common-dir`, not `show-toplevel`.

**Source:** 094e807

---

## Files with Most Lines Changed (2026-05-03)

| File | Lines changed |
|------|--------------|
| docs/claude-code-internals/03-permission-system.md | 370 |
| settings.json | 357 |
| docs/claude-code-internals/04-mcp-integration.md | 334 |
| docs/claude-code-internals/02-tool-system.md | 299 |
| director-mcp/package-lock.json | 298 |
| docs/superpowers/plans/2026-04-26-whisper-call-v0.2.md | 239 |
| docs/claude-code-internals/01-agentic-loop.md | 234 |
| plugins/installed_plugins.json | 159 |
| docs/claude-code-internals/README.md | 77 |
| hooks/context-guard.sh | 71 |

