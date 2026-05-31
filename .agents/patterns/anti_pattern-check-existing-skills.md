---
name: check-existing-skills
type: anti-pattern
confidence: 0.90
source_learnings: [2026-05-02-check-existing-skills-before-designing]
description: Learning: Check Existing Skills Before Designing New Ones
tags: []
---

# Learning: Check Existing Skills Before Designing New Ones

## What We Learned

When tasked with creating a new skill, always read `~/.claude/skills/` and the available skills list in the system-reminder BEFORE entering the brainstorming/design phase. In this session, we designed a full hook-audit skill from scratch, wrote a spec, and wrote an implementation plan — then discovered on post-mortem that `hook-audit` already existed with an `audit.sh`, `flow.dot.template`, and 4-phase workflow.

The existing skill was MORE sophisticated in structure (phase flags, timing estimates, anti-patterns) while our new design added three genuinely missing capabilities (plugin hook discovery, effectiveness via data stores, cache health correlation). 45 minutes of design work was spent on re-invention when 10 minutes of exploration would have redirected it to targeted augmentation.

## Why It Matters

Every session that designs a duplicate skill wastes design + planning time and creates a divergence risk (two skills with the same name or overlapping scope). The skill list is always available in the system-reminder — reading it takes seconds.

## Source

Hook-audit skill design session, 2026-05-02. Discovered on post-mortem when checking if skill files existed.

## How to Apply

Before invoking `superpowers:brainstorming` for a skill:
1. Scan the available-skills list in the system-reminder
2. If a matching skill name exists, invoke `Skill(<name>)` to read current content
3. Design only what's genuinely missing — augment, don't duplicate
