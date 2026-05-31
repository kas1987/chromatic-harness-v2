---
name: 2026-05-02-hook-audit-skill-build
source_ids: [2026-05-02-hook-audit-skill-build]
source_type: learning
confidence: 0.90
suggested_use: RED/GREEN test cycle is the right way to build a skill
canon_map: general
status: pending
tags: []
---

## Summary

RED/GREEN test cycle is the right way to build a skill

## Evidence

# Learning: RED/GREEN test cycle is the right way to build a skill

## What We Learned

Building the hook-audit skill via a RED/GREEN subagent test cycle (run audit.sh against real hooks, find gaps = RED, fix SKILL.md + script until gaps are caught = GREEN) produced a much more grounded skill than spec-first design would have. The RED baseline surfaced 8 real bugs in the live hook config.

## Why It Matters

Skill files written without a real test subject tend to be generic and miss the sharp edges. Running against actual config first makes the skill immediately useful rather than aspirational.

## Source

hook-audit skill build 2026-05-02 (session 4a631e58).

---

# Learning: Hook silent failures are the dominant failure mode

## What We Learned

The most common hook problem found during the hook-audit RED baseline wasn't crashes — it was silent no-ops: `ruff` not on PATH so formatting hooks do nothing, `python` vs `python3` mismatch producing no output, timeouts too short for cold WSL starts. The audit.sh script should check PATH availability for every command, not just file existence.

## Why It Matters

Silent no-ops are worse than crashes: the harness reports success while the hook does nothing. Coverage checks that only verify file existence miss the majority of real failures.

## Source

hook-audit RED baseline findings, 2026-05-02.

---

# Learning: Global PreCompact hook needs explicit timeout

## What We Learned

PreCompact hooks that produce the `hookSpecificOutput` JSON blob have no default timeout in Claude Code — the field must be set explicitly. A missing `timeout` causes the hook to be silently skipped on slow systems.

## Why It Matters

PreCompact hooks that inject compaction guidance are high-value (they shape what context survives compaction). Silently skipping them is costly.

## Source

hook-audit RED baseline, 2026-05-02.
