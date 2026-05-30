# Nightly Extract — 2026-04-27

**Commits processed:** 10 (of 35 in window; window = last 26 hours)  
**Signals found:** 9

---

## Signal 1: CLAUDE.md refactored from Director-prescriptive to Autonomous Operation

**What:** The top-level CLAUDE.md was rewritten. The old version contained imperative Director session-start rituals (call `director_inject_context`, `director_monitor`, etc. on every session open), blocking gate behavior (WARN → ask user, BLOCK → halt), and end-of-session checklists. The new version declares "fully autonomous" mode: proceed without asking, gate checks are informational only (log result, never block on WARN or BLOCK), and the Director MCP section is reduced to a load-on-demand reference.

**Why:** The prescriptive Director rituals were adding latency and friction to every session. The new design externalizes governance to the hook layer and loads Director context only when a `director_*` tool is actually needed.

**Reuse signal:** When CLAUDE.md gate rituals feel like ceremony, move them to optional load-on-demand and document the trigger condition ("load doctrine when first `director_*` tool is needed"). Gate checks belong in hooks, not in the primary instruction file.

**Source commit:** `0733c74` (CLAUDE.md rewrite accompanies hook introduction), diff also visible at `dc62ba7^` baseline

---

## Signal 2: Cloud-vs-local model router as a non-blocking PreToolUse hook

**What:** `hooks/model-router.sh` added as a `PreToolUse` hook matching the `Agent` tool. It reads the dispatch payload (description + prompt + model parameter) from stdin, classifies the intent as `cloud`, `local`, or `reviewer` using regex patterns, then appends a JSONL recommendation to `~/.claude/.agents/router/log.jsonl`. Always exits 0 — it never blocks or rewrites the call.

**Why:** Rewriting the `model` parameter inline would break Claude Code (only `haiku|sonnet|opus` accepted). Logging a recommendation lets a downstream OL layer (Ollama proxy) consume it via side-channel. Projected 27% cost savings (~$71 on the originating session).

**Reuse signal:** When you want to influence routing without changing in-flight tool calls, use a non-blocking hook that writes recommendations to a JSONL side-channel. The consumer can be async and decoupled.

**Source commit:** `0733c74`

---

## Signal 3: Router classification heuristic — 70/30 reference-vs-judgment rule

**What:** The routing decision codifies a heuristic: if a subagent prompt is >70% reference material to copy verbatim and <30% judgment, route local (Haiku/OL). If it asks for novel decisions or analysis of unfamiliar code, route cloud. Three buckets: `local` (scaffold, seed, boilerplate, JSON-to-table, format), `cloud` (brainstorm, design tradeoffs, pre-mortem, debug, root cause, multi-file refactor), `no LLM` (ls, grep, git, jq — use Bash directly).

**Why:** The prior session's 90.7% cache hit rate ($813 saved) must not be broken by mid-conversation model handoffs. Routing via subagent dispatch and hooks (ephemeral side-channels) preserves the cloud cache prefix.

**Reuse signal:** The 70/30 heuristic and the three-bucket classification (local / cloud / no-LLM) are directly reusable in any multi-model orchestration setup. Cache prefix preservation is a first-class concern when routing.

**Source commit:** `0733c74`, patterns in `8d41bb0`

---

## Signal 4: Externalize hook patterns to JSON config with fallback

**What:** `config/router-patterns.json` added. The hook previously had hardcoded bash arrays for `LOCAL_PATTERNS`, `CLOUD_PATTERNS`, `REVIEWER_PATTERNS`. Now it loads them from the JSON file via `jq` + `mapfile`, with the hardcoded arrays as fallback when the config is missing or malformed. `ROUTER_PATTERNS_FILE` env var overrides the config path. `tr -d '\r'` added in mapfile pipeline for Windows CRLF robustness.

**Why:** Closes `rt-nw-003` from post-mortem. Patterns change more frequently than hook logic; externalizing them avoids modifying the hook script for routine tuning.

**Reuse signal:** For any hook with growing regex/pattern sets, externalize to JSON and load with jq + fallback. Always add CRLF stripping when the file may be edited on Windows.

**Source commit:** `8d41bb0`

---

## Signal 5: Router log rotation — atomic mv, keep newest 80%, env-var threshold

**What:** `hooks/model-router.sh` gained log rotation logic. When `log.jsonl` exceeds `ROUTER_MAX_LOG_LINES` (default 2000, overridable via env), it keeps the newest 80% of lines via `tail -n`, writes to a tmp file, then `mv` atomically replaces the log. The `settings.json` `env` block sets `ROUTER_MAX_LOG_LINES=500` for this project.

**Why:** Closes `rt-nw-004`. Without rotation, the log grows unboundedly. Keeping 80% (vs 50%) preserves more recency context for the OL consumer while still bounding size.

**Reuse signal:** For any append-only JSONL hook log: rotate at configurable line count, keep newest 80%, use atomic `tmp + mv`. Expose the threshold as an env var set in `settings.json`.

**Source commit:** `36a7472` (rotation logic), `f8828c5` (env var in settings), `47026cf` (consumer position reset on rotation)

---

## Signal 6: router-tail.py — stdlib-only live observer for hook side-channel logs

**What:** `scripts/router-tail.py` (~73 lines, stdlib only) tails `log.jsonl` with colorized output. Flags: `--since` (ISO timestamp filter), `--no-color`. Intended for interactive use to observe what the router hook is recommending before wiring OL integration.

**Why:** Closes `rt-nw-001`. A developer needs to verify the hook is classifying correctly before building the OL consumer. A dedicated tail script with color is faster than raw `tail -f | jq`.

**Reuse signal:** Any hook writing a JSONL side-channel log should ship a companion `*-tail.py` (stdlib only, --since, --no-color) for live observation during setup and debugging.

**Source commit:** `e8c9dd8`

---

## Signal 7: Whisper Call — two-tier MCP + plugin architecture for OS dictation

**What:** Full `whisper-flow-mcp` TypeScript MCP server + `whisper-call` Claude Code plugin implementing Wispr Flow dictation integration. MCP server (TypeScript 5, `@modelcontextprotocol/sdk`, `nut-js` for hotkeys, `clipboardy`) handles durable state, OS-level integration, and governance (hard-block list). Plugin (Python scripts) provides slash commands (`/call`, `/call mode`, `/call macro`, `/call template`), routing logic, macro expansion, audit log, and template library (7 seed templates).

**Why:** Separates OS-level concerns (hotkey simulation, clipboard polling, state persistence) from Claude Code interface concerns (slash commands, routing). The MCP server can be reused by other plugins or clients.

**Reuse signal:** When building voice/OS integrations: TypeScript MCP server for OS-level + state, Python plugin scripts for Claude Code interface. Hard-block governance lives in the MCP layer; routing/macro expansion lives in the plugin. Two-tier pattern isolates OS coupling.

**Source commit:** `9d3596a` (scaffold) through `75d5260` (Popen fix) — ~20 commits

---

## Signal 8: GitHub Actions CI for mixed TypeScript + Python test suites

**What:** `.github/workflows/whisper-call.yml` runs vitest (MCP, 32 tests) and pytest (plugin, 33 tests) in parallel, triggered on push/PR touching relevant paths. 65/65 tests pass at ship.

**Why:** Closes `wc-nw-002`. Mixed-language projects (TS MCP + Python plugin) need CI that runs both suites without assuming a single toolchain. Path filtering ensures CI only runs when relevant files change.

**Reuse signal:** For TS MCP + Python plugin projects, use parallel jobs in the same workflow with path filters. Don't couple vitest and pytest into a single job — parallel execution is faster and failures are easier to triage.

**Source commit:** `6c3e8e7`

---

## Signal 9: Hard-block governance parity test pattern

**What:** `whisper-flow-mcp/src/__tests__/governance-parity.test.ts` (~244 lines) added as `wc-nw-001`. Tests that the MCP server's governance classifier produces identical hard-block decisions to the plugin's Python governance list. Cross-language parity test via shared fixture data.

**Why:** When governance enforcement is split across two languages/runtimes, a parity test catches drift early. The test uses the same input fixtures and asserts identical outputs from both classifiers.

**Reuse signal:** For any governance/hard-block logic duplicated across languages: write a parity test that runs both implementations on the same inputs and diffs the results.

**Source commit:** `2d8628a`

---

## Files with Most Lines Changed Today

| File | Lines |
|------|-------|
| `docs/superpowers/plans/2026-04-26-whisper-call-implementation.md` | 3318 |
| `scripts/router-consumer.py` | 457 |
| `docs/superpowers/specs/2026-04-26-whisper-call-design.md` | 442 |
| `tests/router-hook.sh` | 301 |
| `whisper-flow-mcp/src/__tests__/governance-parity.test.ts` | 244 |
| `plugins/whisper-call/scripts/call_driver.py` | 222 |
| `hooks/model-router.sh` | 175 |
| `whisper-flow-mcp/src/index.ts` | 120 |
| `settings.json` | 119 |
| `CLAUDE.md` | 118 |
