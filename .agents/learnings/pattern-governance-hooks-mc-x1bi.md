---
name: governance-hooks-mc-x1bi
type: pattern
confidence: 0.90
source_learnings: [2026-05-28-governance-hooks-mc-x1bi]
description: Learning: Substring Matching Insufficient for Security Hooks
tags: []
---

# Learning: Substring Matching Insufficient for Security Hooks

## What We Learned

Security hooks that use substring matching on shell command strings produce false positives when the blocked marker appears in read-only operations (grep, echo, python validation). Segment-level scanning with a safe-prefix exclusion list is required.

## Why It Matters

A naively written deny-list hook blocks legitimate work the moment it goes live — including the very commands used to validate it. Creates emergency mid-implementation fixes under pressure.

## Source

policy_gate.py initial draft in mc-x1bi.2 — blocked `grep "git push --force" file.sh` until fixed.

---

# Learning: Write Issues Against Reality, Not Plans

**ID**: L2
**Category**: process
**Confidence**: high

## What We Learned

Issues that say "change line N of X" imply X exists. When X is a planned (not-yet-created) file, workers waste time searching. Write "Create X with behavior Y" for new files.

## Why It Matters

Eliminates worker confusion and prevents misclassification (modification vs creation).

## Source

mc-x1bi.3 described modifying "lines 56 and 74" of review-dispatch.sh which did not exist yet.

---

# Learning: Pre-Mortems With Pseudocode Outperform Abstract Warnings

**ID**: L3
**Category**: process
**Confidence**: high

## What We Learned

Both mc-x1bi pre-mortem predictions were mitigated with zero debugging time because pseudocode solutions were provided alongside the warnings — not just risk names.

## Why It Matters

An actionable pre-mortem is an implementation asset; a vague one is noise.

## Source

pm-20260528-001 (crash guard) and pm-20260528-002 (curl mock) both applied exactly as specified.

---

# Learning: PreToolUse Hooks Activate for Current Session Immediately

**ID**: L4
**Category**: architecture
**Confidence**: high

## What We Learned

Wiring a hook into settings.json makes it live for the current session instantly — not just on next session start. Test hook logic in isolation before registering, or the hook will intercept its own smoke test commands.

## Why It Matters

Prevents the hook from blocking validation of itself.

## Source

policy_gate.py started blocking bash tool calls immediately after settings.json was updated.

---

# Learning: git init Propagates Template Hooks Fleet-Wide

**ID**: L5
**Category**: architecture
**Confidence**: medium

## What We Learned

Re-running `git -C <dir> init` on an existing repo re-applies git template hooks. This is a reliable propagation mechanism requiring no per-repo manual copy.

## Why It Matters

Enables fleet-wide hook updates cleanly.

## Source

mc-x1bi.1 — template fix propagated to ~/chromatic-stack via git init.
