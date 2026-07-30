# Agents Quick Start — Chromatic Harness V2

> **START HERE on every new session.** This page is the 60-second version of [AGENTS.md](../AGENTS.md) and [AGENT_OPERATIONS.md](../AGENT_OPERATIONS.md).

## What happens automatically when you launch

Claude Code sessions in this repo run the **SessionStart** hook chain from `.claude/settings.json`:

1. `python scripts/session_start.py` — emits telemetry, surfaces prior learnings, prints the `bd ready` queue, reads `.agents/handoffs/latest.json`, runs the unified guard, and prints manifest/health/budget/baseline status.
2. `python scripts/hooks/session_priority_check.py` — injects the **P1–P4 priority gate**:
   - **P1** = must do now (breakage, blocker, critical path)
   - **P2** = should do this session (planned work, open beads)
   - **P3** = nice to have (improvements, cleanup)
   - **P4** = idea only — add to `01_STATE/P4_PARKING_LOT.md`, do **not** execute

The harness therefore defaults to the **Agents workflow on launch**: work is pulled from beads (`bd`), not from chat TODOs.

## Your first 60 seconds

```bash
# 1. Prime the bead index (also runs automatically on PreCompact)
bd prime

# 2. See what is ready to work on
bd ready

# 3. Claim a bead before you start editing files
bd update <bead-id> --claim

# 4. Do the work inside the bead's scope
# 5. Close the bead when done
bd close <bead-id>
```

## Launch-to-Agents wiring at a glance

| File | Purpose |
|------|---------|
| `.claude/settings.json` | SessionStart / SessionEnd / PreCompact / PreToolUse hooks |
| `scripts/session_start.py` | Boot, handoff, `bd ready`, telemetry, budget forecast |
| `scripts/hooks/session_priority_check.py` | P1–P4 priority gate injection |
| `AGENTS.md` | Mandatory agent rules |
| `AGENT_OPERATIONS.md` | Full checklist: start → work → push → handoff |
| `00_SOURCE_OF_TRUTH/HARNESS_EXECUTION_FLOW.md` | Canonical execution flow |

## Agnes provider default

If no local provider is available and the task is online C2/C3/C4, the router promotes **Agnes** to first choice (`provider_selector._apply_agnes_default`). This is configurable via `config/routing/user-preferences.yaml`:

```yaml
provider_preference: agnes   # or "gemini", "ollama_local", "native_claude", etc.
agnes_default: true          # set false to disable the C2+ Agnes promotion
```

See [docs/routing/API_ROUTING_POLICY.md](../docs/routing/API_ROUTING_POLICY.md) for the full provider priority ladder and [docs/routing/MODEL_REDUNDANCY_AND_TOKEN_EFFICIENCY.md](../docs/routing/MODEL_REDUNDANCY_AND_TOKEN_EFFICIENCY.md) for redundancy and token-efficiency rules.

## End-of-session minimum

1. Run tests if you changed code.
2. Run `python scripts/workflow_git.py plan`.
3. If confidence ≥ 88, tests green, and risk is not high/critical, push with `ship --execute` — do not wait for a separate "please push".
4. Update/close beads.
5. Write or refresh `12_HANDOFFS/SESSION_COMPACT.md` and `.agents/handoffs/latest.json`.
