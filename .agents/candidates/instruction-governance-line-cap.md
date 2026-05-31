---
name: instruction-governance-line-cap
source_ids: [2026-05-30-instruction-governance-line-cap]
source_type: principle
confidence: 0.85
suggested_use: Auto-appended instruction prose silently breaks the CI docs guard
canon_map: knowledge
status: pending
tags: []
---

## Summary

Auto-appended instruction prose silently breaks the CI docs guard

## Evidence

# Auto-appended instruction prose silently breaks the CI docs guard

## Observation

`CLAUDE.md` grew to 50 lines after an auto-mode commit appended an "Autonomous
Operation" block. `scripts/validate_instruction_governance.py` caps `CLAUDE.md` at 45
lines, and `scripts/check_agent_operations.py` runs that validator — which CI runs in
its "Agent operations guard" step. So a config-doc edit failed **every clean CI run
before any test ran**, and the failure surfaced two steps removed from the cause.

## Evidence

- `python scripts/check_agent_operations.py` → `CLAUDE.md has 50 lines (max 45)`.
- Independent reviewers (Codex, Copilot) reproduced and flagged the same cap.
- Fix: condense to a one-line pointer (doctrine already lives in global
  `~/.claude/CLAUDE.md` + `AGENT_OPERATIONS.md`); 50 → 44 lines, guard green.

## Recommendation

- Instruction files (`CLAUDE.md`, `AGENTS.md`, rules) have **hard line caps** enforced
  in CI. Keep them as pointers; put prose in `AGENT_OPERATIONS.md` or global config.
- Auto-mode / agents that *append* to instruction files must respect the cap — append
  blindly and you red-light CI for everyone.
- When a guard fails on a file you didn't knowingly change, check for an auto-mode commit
  that rode onto the branch (these sweeps are common in this harness).
