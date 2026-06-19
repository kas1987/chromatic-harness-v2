# GO Loop Skill: Auto-Activation and Trigger Injection

**Bead:** mc-rfdbp (CC #34)  
**Status:** Design v1.0  
**Date:** 2026-06-19

---

## Overview

The GO Loop is the Chromatic Harness's autonomous execution mode. When activated, the agent continuously claims and closes beads from `bd ready` without pausing for human approval between tasks. This document defines when the GO Loop activates, how triggers inject into the loop, and what governs exit.

---

## Auto-Activation Conditions

The GO Loop activates when ALL of the following are true:

| Condition | Check |
|-----------|-------|
| `bd ready` returns ≥1 task | `bd ready` non-empty |
| No `BLOCKED` tasks ahead of queue head | queue head is `ready` |
| Governance files present | `workstream-registry.yaml` readable |
| No active `CLAUDE_PREFLIGHT_STRICT` block | preflight passes |
| User has not issued a STOP signal | no `~/.claude/.agents/STOP` file |

Auto-activation is **suppressed** when:
- Last task closed with `blocked` label (manual review needed)
- Token budget within 20% of daily cap (conservative mode)
- `AUTO_MODE_*` flags are `false` in `settings.json`

---

## Trigger Injection

External systems can inject triggers into the GO Loop via the dispatch queue:

### Hook-Triggered Dispatch

Pre-push preflight and review-daemon findings write to `.dispatch/`:

```bash
# cross-repo-preflight.sh (on preflight fail)
echo '{"task_id":"auto-pf-001","title":"Fix preflight: governance header missing","c_level":"C2","priority":"P1"}' \
  >> .dispatch/auto-pf-001.json
```

The GO Loop polls `.dispatch/` every 30s. New entries are claimed immediately (bypassing priority sort — injected tasks run next).

### Cron-Triggered Dispatch

Multica autopilot runs on `*/2` cron. On each tick it:
1. Reads `bd ready` for tasks tagged `multica`
2. Writes dispatch entries for any not already `in_progress`
3. GO Loop picks them up on next poll

### Manual Trigger

```bash
# Inject a one-shot task into a running GO Loop
echo '{"task_id":"manual-001","title":"Check routing table","c_level":"C2","priority":"P0"}' \
  > .dispatch/manual-001.json
```

Priority `P0` means the loop picks this up before anything else in `bd ready`.

---

## Loop Lifecycle

```
START
  │
  ▼
poll bd ready + .dispatch/
  │
  ├── empty? → idle (30s backoff) → poll again
  │
  ▼
claim head task
  │
  ├── claim fails (already claimed)? → skip → poll again
  │
  ▼
execute task
  │
  ├── success → bd close --reason "..." → loop
  │
  ├── blocked → bd label add blocked → PAUSE (notify user)
  │
  └── timeout → bd label add timed-out → loop (continue)
```

---

## Exit Conditions

The GO Loop exits cleanly when:

1. **STOP file**: `touch ~/.claude/.agents/STOP` — loop exits after current task completes
2. **Empty queue**: `bd ready` returns empty AND `.dispatch/` is empty — loop exits with summary
3. **Budget guard**: remaining tokens < 20% of session cap — loop exits conservatively
4. **Consecutive blocks**: 3 consecutive `blocked` outcomes — loop pauses and notifies

On exit, the loop writes a summary to `.agents/events/go-loop-summary-<timestamp>.json`:

```json
{
  "tasks_completed": 6,
  "tasks_blocked": 1,
  "exit_reason": "queue_empty",
  "total_duration_s": 847
}
```

---

## Skill Invocation

The GO Loop is invoked as a skill in Claude Code:

```
/go-loop [--dry-run] [--max-tasks N] [--c-level C2]
```

Flags:
- `--dry-run`: show what would run, don't execute
- `--max-tasks N`: exit after N completions (default: unlimited)
- `--c-level C2`: only process tasks at or below this C-level

---

## Related

- `AGENT_CONTROL_LOOP.md` — queue protocol and task state machine
- `cross-repo-preflight.sh` — trigger injection on preflight failures
- `.agents/STOP` — emergency stop signal
