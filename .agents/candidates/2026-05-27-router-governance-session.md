---
name: 2026-05-27-router-governance-session
source_ids: [2026-05-27-router-governance-session]
source_type: learning
confidence: 0.90
suggested_use: Router Advisory vs Enforcement Gap
canon_map: general
status: pending
tags: []
---

## Summary

Router Advisory vs Enforcement Gap

## Evidence

# Learning: Router Advisory vs Enforcement Gap

## What We Learned

`model-router.sh` is advisory-only for native Claude Code sessions. `permissionDecision: deny` blocks Agent spawns but cannot change the underlying model Claude runs. Pattern-based tier scoring over free-text description strings has a ~65% miss floor. The reliable enforcement path is `model_tier:` in skill frontmatter + a hook that reads it directly (mc-6a5.2).

## Why It Matters

Confusing "router log says tier-2" with "agent actually ran on GPT-4o-mini" leads to false assumptions about cost savings. The router's real value is: (a) blocking obvious misroutes before spawn, (b) providing visibility for the OL dispatch layer.

## Source

Session: router alignment audit — model-router.sh + router-patterns.json v3

---

# Learning: Council Judge Routing Was Silently Broken

## What We Learned

Judges with `subagent_type=general-purpose`, no tool-use keywords in description, and matching a tier-2 pattern (`council.*judge`) were being DENIED by the PreToolUse hook. Bug was invisible because some councils used `subagent_type="claude"` which bypassed the deny condition. Fix: move judge patterns to tier-4 and add `caller_explicit_model` guard.

## Why It Matters

Silent denials in council break the post-mortem and pre-mortem workflows without any error surfaced to the user. The deny block must never fire when the caller has explicitly named a Claude model alias.

## Source

Session: router alignment audit — log analysis showing tier-2 for judge descriptions with req=sonnet

---

# Learning: Heredoc Quoting — Write Script to File Pattern

## What We Learned

Passing multi-line Python (or any script with string literals) to bash via `bash -c << 'HEREDOC'` fails when the Python contains single-quoted strings. Pattern that always works: `cat > /tmp/script.py << 'MARKER'` then `python3 /tmp/script.py`. Single-quoted HEREDOC marker means bash does zero interpolation; the script lands verbatim.

## Why It Matters

This trap recurs in automation scripts that inject governance sections, frontmatter, or other structured content into files. Write-to-file-then-execute is the zero-surprise pattern.

## Source

Session: Tool Governance injection — prior session failure resolved by writing Python to temp file

---

# Learning: Harness as Living Contract

## What We Learned

Converting behavioral properties into BATS tests makes them permanent contracts. S19 (Tool Governance exists in all 13 skills), S20–S23 (router behavior) cannot silently regress. Each test encodes a past failure mode as a future gate.

## Why It Matters

Without the harness tests, the router fix and governance injection would be invisible to future sessions. The BATS suite is the lowest-cost way to prevent rediscovery of already-solved problems.

## Source

Session: harness-settings.bats S19–S23 addition
