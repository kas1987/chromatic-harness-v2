---
name: 2026-05-24-nightly-extract
type: principle
confidence: 0.50
source_learnings: [2026-05-24-nightly-extract]
description: Nightly Extract — 2026-05-24
tags: []
---

# Nightly Extract — 2026-05-24

**Commits processed:** 7 (5c2706b → 624b9d6)
**Signals found:** 6

---

## Signal 1 — Policy-gate pattern: tiered allow/ask/deny for PreToolUse hooks

**What:** `hooks/policy_gate.py` implements a three-tier decision engine for PreToolUse hook payloads. Bash commands are classified against explicit safe-prefix, ask-marker, and deny-marker lists. File-write tools (Edit, Write, MultiEdit) are classified against allowed/restricted/denied path prefixes and filenames. Unknown tools return `defer`.

**Why:** Claude Code permission prompts interrupt flow. A static classification layer—fast, dependency-free, no LLM call—can pre-approve clearly safe commands and pre-block clearly dangerous ones, surfacing only ambiguous cases for human review.

**Reuse signal:** Drop `hooks/policy_gate.py` into any repo. Wire it as a PreToolUse hook on Bash/Edit/Write via `settings.json` (see `.claude/settings.example.json`). Extend `SAFE_BASH_PREFIXES`, `ASK_BASH_MARKERS`, `DENY_BASH_MARKERS`, and path lists for the target repo's needs.

**Source:** `5c2706b`, `9ce6727`

---

## Signal 2 — AGENTS.md contract: explicit allowed/restricted/denied work sections

**What:** `AGENTS.md` defines agent behavioral contract as three clearly labelled sections: *Allowed Work* (paths agents may freely edit), *Restricted Work* (requires asking before proceeding), *Denied Work* (hard no-ops). The same taxonomy mirrors the policy_gate tiers.

**Why:** Prose rules get misinterpreted. Explicit list-based sections let both humans and automated policy gates derive the same decision from one canonical source. Mirrors CLAUDE.md but is agent-facing.

**Reuse signal:** Template `AGENTS.md` with the three sections for any repo where autonomous agents operate. Keep the Denied section brief and absolute; keep Restricted as the catch-all for "ask first."

**Source:** `5c2706b`

---

## Signal 3 — File-backed TTL state machine for conditional hook chains

**What:** `hooks/chain_state.py` provides a lightweight file-backed state helper. A trigger hook (hook 1) writes a JSON blob to `.state/hooks/<session>.<chain>.json` with an `expires_at_epoch`. A worker hook (hook 2) reads that state and only acts if stage ≥ 1 and the state has not expired. A reset hook (hook 3) clears the state.

**Why:** Claude hooks are event-driven, not dependency-driven—there's no native way to say "run hook B only after hook A fired." File-backed TTL state solves this without a daemon or network dependency. TTL (default 120 s) prevents stale state from leaking across sessions.

**Reuse signal:** For any multi-step conditional automation in Claude hooks: import `chain_state.py`, set `HOOK_STATE_DIR` and `HOOK_CHAIN_TTL_SECONDS` env vars, and implement the 3-hook pattern. The `.state/hooks/` directory must be gitignored.

**Source:** `5fb9b0f`

---

## Signal 4 — Dependency-free JSONL audit logger callable from shell hooks

**What:** `hooks/audit_log.py` appends canonical AgentOps JSONL events. It accepts all event fields as CLI flags or via stdin. No third-party dependencies. `hooks/audit-logger.sh` is a thin Bash wrapper for log rotation + simple "tool executed" lines.

**Why:** Hook scripts run in minimal environments where importing heavy SDKs is unreliable. A stdlib-only Python emitter keeps observability available everywhere. JSONL is append-only, grep-friendly, and trivially ingestible into SQLite/DuckDB.

**Reuse signal:** Call `python hooks/audit_log.py --event-type <type> --source-component <component> --payload '<json>'` from any hook. Pair with `observability/ingest_jsonl.py` to push into SQLite for ad-hoc queries.

**Source:** `b42d678`, `9ce6727`

---

## Signal 5 — Usage-tracker.sh: Stop hook that parses transcript for token counts

**What:** `hooks/usage-tracker.sh` is a PostToolUse/Stop event handler. It reads `transcript_path` from the Stop event, converts Windows-style paths to bash paths, parses the JSONL transcript with embedded Python (deduplicating by `requestId`), and writes cumulative token totals to `~/.claude/usage-tracker.json`.

**Why:** Claude Code doesn't expose per-session cost summaries natively. Parsing the transcript file in the Stop hook captures actual token usage at session end without requiring API instrumentation.

**Reuse signal:** Wire to the `Stop` hook in `settings.json`. Extend the embedded Python to track additional fields (e.g., model-specific costs). Requires `jq` on PATH.

**Source:** `d384b40`

---

## Signal 6 — E2E baseline snapshot: store pass/fail counts in `.agents/baselines/`

**What:** `.agents/baselines/e2e-2026-05-24.json` is a small JSON file recording the E2E harness result: date, pass/fail counts, and run metadata. `.gitignore` updated to track the baselines directory but exclude runtime logs.

**Why:** Keeping dated JSON snapshots in the repo creates a lightweight audit trail of test health over time without requiring a CI database. The nightly harness commit pattern ("chore(e2e): nightly harness baseline") makes baseline history grep-able from git log.

**Reuse signal:** Add a `post-e2e` step that writes `{ date, pass, fail, duration_ms }` to `.agents/baselines/YYYY-MM-DD.json` and commits with `chore(e2e): nightly harness baseline`. Pair with a `.gitignore` that includes `baselines/` but excludes `logs/`.

**Source:** `624b9d6`

---

## Files with most lines changed today

| File | Lines changed |
|---|---|
| `hooks/policy_gate.py` | 176 → 210 (net +34 via integration) |
| `docs/implementation-tracking-log.md` | +156 |
| `docs/hook-chain-state-machine.md` | +141 |
| `observability/sqlite_schema.sql` | +86 |
| `tests/test_hook_chain_state.py` | +108 |
| `hooks/chain_state.py` | +79 |
| `observability/ingest_jsonl.py` | +98 |
| `docs/permission-matrix.md` | +122 |
| `AGENTS.md` | +69 |
| `hooks/audit_log.py` | +91 |

