# Nightly Extract — 2026-05-22

**Commits processed:** 10 (51a3755 ba298f2 8c3b018 893102d d238830 e5c62f2 128f8c5 3dd4797 eb42ad8 bc57144)
**Signals found:** 10

---

## Signal 1: Slash-command trinity for daily ops

**What:** Added three project-level slash commands — `/daily` (morning vibe + PRs + queue), `/weekly` (E2E + vibe + queue review + session health), `/e2e` (harness run + pass/fail report). All three are zero-questions, machine-parseable output.

**Why:** No standard, always-available path to check repo health quickly. Commands needed to be headless-compatible (same output format whether run interactively or by cron).

**Decision:** Structured output block with fixed fields (`Vibe:`, `PRs:`, `Queue:`, `E2E:`, `Health:`) so downstream scripts can grep results; strict "no follow-up questions" directive.

**Reuse signal:** Drop-in template for any Claude Code project needing daily/weekly quality loops. Copy `.claude/commands/{daily,weekly,e2e}.md`, adjust queue path and repo slug.

**Source:** `51a3755` — `.claude/commands/daily.md`, `.claude/commands/weekly.md`, `.claude/commands/e2e.md`

---

## Signal 2: Headless audit cron (always-exit-0 wrapper)

**What:** `bin/headless-audit.sh` wraps E2E + session-health + queue snapshot; always exits 0 and logs to `.agents/audits/YYYY-MM-DD-headless.log`. `bin/register-weekly-audit.ps1` registers a Sunday 08:00 Windows Task Scheduler job.

**Why:** Weekly audits only happened when initiated manually. The scheduler fires even when no session is open.

**Decision:** `exit 0` unconditionally so a failing E2E never breaks Task Scheduler; failures are surfaced in the log, not via exit code.

**Reuse signal:** Any Windows-hosted Claude Code project wanting background health checks. Change `CLAUDE_DIR` path and cron frequency in the ps1 registration script.

**Source:** `51a3755` — `bin/headless-audit.sh`, `bin/register-weekly-audit.ps1`

---

## Signal 3: Federated governance YAML (machine-readable policy)

**What:** `governance/auto-mode-scope.yaml` encodes T1–T4 authorization tiers, path globs, and approval rules. `governance/multi-router-matrix.yaml` encodes all-IDE routing decisions. Both are federated from `C:\.01_Image Org` via `pnpm run governance:*:federate`.

**Why:** Policy was prose-only in CLAUDE.md; hooks and other IDEs (Cursor, Codex) had no machine-readable source of truth.

**Decision:** Separate YAML with explicit `policy_version` and `federation_roots`; hooks read the files at runtime, CLAUDE.md references the path. Federation command keeps all repos in sync.

**Reuse signal:** Multi-repo setups where the same autonomy/routing policy must apply everywhere. Canonicalize in one repo, federate via npm/pnpm script.

**Source:** `ba298f2` — `governance/auto-mode-scope.yaml`, `governance/multi-router-matrix.yaml`, `.claude/config/provider-tiers.json`, `.claude/config/router-patterns.json`

---

## Signal 4: session-health.sh — fail-open pre-flight at SessionStart

**What:** `hooks/session-health.sh` runs at every SessionStart; checks gh auth status, bd CLI presence, and raw PAT presence in `settings.json`; writes `~/.claude/.agents/router/session-health.json`. Always exits 0.

**Why:** Sessions could silently start in broken state (revoked auth, missing CLI, leaked secret) with no warning until a tool call failed.

**Decision:** Three targeted checks only (no heavy scanning); `exit 0` always so a broken toolchain never blocks Claude from starting; JSON output enables `/weekly` to surface status without re-running the hook.

**Reuse signal:** Universal Claude Code SessionStart hook. The PAT leak check (`grep -qE 'ghp_[A-Za-z0-9]{36}'`) catches a common secret-exposure mistake.

**Source:** `8c3b018` — `hooks/session-health.sh`, `hooks/tests/session-health.bats`

---

## Signal 5: rpi-preflight.sh — guard orchestrators to real codebases

**What:** `hooks/rpi-preflight.sh` checks cwd for 9 project markers (`go.mod`, `package.json`, `pyproject.toml`, `Cargo.toml`, `.git`, `pom.xml`, `build.gradle`, `Makefile`, `CMakeLists.txt`); exits 1 with JSON if none found.

**Why:** `/rpi`-style orchestrators launched from a home directory or temp folder would run against no codebase and produce nonsensical output.

**Decision:** Non-blocking (Claude decides what to do with exit 1); JSON stdout allows the caller to surface the error to the user cleanly.

**Reuse signal:** Gate any orchestrator or code-analysis hook that requires a real project directory. The 9-marker list covers most ecosystems.

**Source:** `8c3b018` — `hooks/rpi-preflight.sh`, `hooks/tests/rpi-preflight.bats`

---

## Signal 6: CLAUDE.md P1 patches — four autonomy & environment sections

**What:** Added `Workflow Autonomy` (no mid-skill `AskUserQuestion`), `Pre-Build Checks` (existence check before new skill/hook), `Scope Discipline` (stay on task, note sidequests), `Environment Notes` (Windows 11/WSL, tool paths, push-to-main block, PAT scrub rule).

**Why:** Claude was surfacing confirmation prompts mid-skill, creating duplicate tools, and drifting to adjacent issues. Windows-specific details (bd/ao/bats paths) were undocumented.

**Decision:** Hard prohibitions in system prompt rather than relying on model judgment; environment facts as constants rather than rediscovery each session.

**Reuse signal:** Template for Windows/WSL Claude Code CLAUDE.md. The "existence check before creating" rule prevents tool sprawl in any repo.

**Source:** `893102d` — `CLAUDE.md`

---

## Signal 7: injection-guard.sh — global non-blocking PreToolUse scan

**What:** `hooks/injection-guard.sh` is a null-matcher PreToolUse hook (fires on every tool call); scans all `tool_input` string values (recursively up to depth 5) for 10 injection patterns; emits `additionalContext` warning if matched; always exits 0.

**Why:** External content in tool results (GitHub comments, file contents) could contain injection attempts. A blocking hook would be too disruptive; a non-blocking one at least surfaces the threat.

**Decision:** Recursive string extraction with depth guard (prevents malicious deep nesting from hanging); log-and-warn pattern never interrupts legitimate use.

**Reuse signal:** Drop into any Claude Code project as a defense-in-depth measure. Extend `INJECTION_PATTERNS` array for domain-specific threats.

**Source:** `3dd4797` — `hooks/injection-guard.sh`

---

## Signal 8: Per-field jq assertions in BATS (fix for comma-expression gate)

**What:** T18 previously used `jq -e '.field1, .field2, .field3'` — only the last expression determines exit code. Fixed by splitting into separate `jq -e '.fieldN'` assertions per field in the BATS test. Also renamed `provider` → `target_provider` in `model-router.sh` log output to match schema contract.

**Why:** The comma-list pattern silently passes tests when early fields are null/missing, giving false confidence in schema compliance.

**Decision:** One assertion per field. Schema field names in the hook and test must be identical — any rename must touch both.

**Reuse signal:** Any BATS test validating JSON output schema. Always assert each required field individually, never chain with commas.

**Source:** `d238830` — `hooks/tests/model-router.bats`, `hooks/model-router.sh`

---

## Signal 9: Ollama liveness at SessionStart + tier-0→tier-1 fallback tests

**What:** `hooks/ollama-liveness.sh` wired to `SessionStart` (5s timeout); writes `~/.claude/.agents/router/ollama-status.json` before any Agent dispatch. T23 test verifies tier-0 bumps to tier-1 when Ollama is unreachable; T24 verifies tier-2+ is unaffected.

**Why:** Model router could dispatch tier-0 (Ollama) blind to a down instance, causing delayed failures after prompt round-trips.

**Decision:** Probe at session open, not at dispatch time; status file is shared state for the router. T24 (non-regression for cloud tiers) is as important as T23 (fallback test).

**Reuse signal:** Any multi-provider setup with an optional local model. Wire liveness before first Agent use; use the status file to avoid per-dispatch probes.

**Source:** `e5c62f2` — `hooks/tests/model-router.bats`, `settings.json`

---

## Signal 10: Gitignore runtime state (usage-data/, daemon files)

**What:** Added `usage-data/`, `daemon/`, `daemon.lock`, `daemon.status.json`, `.last-cleanup`, `jobs/` to `.gitignore`; untracked ~105 existing files with `git rm --cached`.

**Why:** Per-session JSON + HTML reports grew unboundedly (each session generates multiple files). Runtime state is not history worth preserving in VCS.

**Decision:** Gitignore + untrack without deleting; files remain on disk for local tooling.

**Reuse signal:** Any repo accumulating ephemeral session/runtime logs. Check `git ls-files` periodically for accidentally-tracked runtime state.

**Source:** `128f8c5` — `.gitignore`

---

## Files with Most Lines Changed Today (non-usage-data)

| File | Lines changed |
|------|--------------|
| `scripts/insights-to-pdr.py` | 290 |
| `hooks/multi-provider-dispatch.sh` | 232 |
| `hooks/tests/model-router.bats` | 225 |
| `hooks/model-router.sh` | 207 |
| `plugins/installed_plugins.json` | 180 |
| `governance/multi-router-matrix.yaml` | 130 |
| `hooks/tests/multi-provider-dispatch.bats` | 129 |
| `hooks/tests/harness-settings.bats` | 126 |
| `plugins/whisper-call/tests/test_mcp_integration.py` | 107 |
| `governance/auto-mode-scope.yaml` | 105 |
