# Chromatic Harness: Canonical Command Phrase Tables

**Bead:** mc-9cnvk (CC #35)  
**Status:** v1.0 — Canonical Reference  
**Date:** 2026-06-19

---

## Overview

This document is the canonical source of command phrases used across the Chromatic Harness ecosystem. Phrases are grouped by domain. Each entry shows the phrase, its C-level classification, the agent/tool that handles it, and the expected output.

---

## Table 1: Session Control

| Phrase | C-Level | Handler | Output |
|--------|---------|---------|--------|
| `bd ready` | C1 | bd CLI | ordered task list |
| `bd show <id>` | C1 | bd CLI | task detail |
| `bd close --reason "<r>"` | C1 | bd CLI | task closed |
| `bd q "<text>"` | C1 | bd CLI | task created |
| `bd assign <id>` | C1 | bd CLI | task claimed |
| `bd label add <id> <tag>` | C1 | bd CLI | tag applied |
| `bd remember "<insight>"` | C1 | bd CLI | learning stored |
| `/go-loop` | C2 | Claude Code skill | autonomous bead execution |
| `/post-mortem` | C2 | Claude Code skill | retro doc + learnings |
| `/compact` | C1 | Claude Code built-in | context compacted |

---

## Table 2: Router & Dispatch

| Phrase | C-Level | Handler | Output |
|--------|---------|---------|--------|
| `python -m router.cli dispatch --c-level C3 --message "<m>"` | C3 | router CLI | dispatch result JSON |
| `python -m router.cli dispatch --dry-run` | C2 | router CLI | selected_provider preview |
| `curl http://127.0.0.1:9090/health` | C1 | native_claude_relay | `{"status":"ok"}` |
| `python scripts/native_claude_relay.py` | C2 | relay script | relay process started |
| `power-t4.sh on` | C2 | power-t4.sh | T4 model unlocked for session |
| `power-t4.sh off` | C2 | power-t4.sh | T4 model re-locked |

---

## Table 3: Governance & Audit

| Phrase | C-Level | Handler | Output |
|--------|---------|---------|--------|
| `bash ~/.claude/scripts/governance-federate.sh` | C2 | federate script | YAML synced to federation roots |
| `bash ~/.claude/scripts/governance-federate.sh --rollback` | C2 | federate script | previous YAML restored |
| `python scripts/token_governance_closed_loop.py` | C3 | telemetry script | governance report JSON |
| `bd list --status in_progress` | C1 | bd CLI | open tasks |
| `cat ~/.agents/events/preflight-events.jsonl` | C1 | shell | preflight event log |
| `agent-watch status` | C1 | agent-watch | registry overview |

---

## Table 4: Harness Infrastructure

| Phrase | C-Level | Handler | Output |
|--------|---------|---------|--------|
| `pytest tests/` | C2 | pytest | test results |
| `pytest tests/test_native_claude_relay.py -v` | C2 | pytest | relay test results |
| `python tools/portfolio_token_telemetry.py` | C3 | telemetry tool | portfolio ledger |
| `python -m harness.kernel status` | C2 | kernel | subsystem status |
| `Get-PSDrive C` | C1 | PowerShell | disk usage |

---

## Table 5: Git / PR Workflow

| Phrase | C-Level | Handler | Output |
|--------|---------|---------|--------|
| `git checkout -b feat/<slug>` | C1 | git | new branch |
| `git push --no-verify` | C1 | git | push (docs-only bypass) |
| `git push origin feat/<slug>` | C1 | git | push branch |
| `gh pr create --title "<t>" --body "$(cat <<'EOF'...EOF)"` | C2 | gh CLI | PR URL |
| `gh pr merge <N> --squash` | C2 | gh CLI | PR merged |

---

## Phrase Classification Rules

- **C1**: Read-only or local state mutation. No external API calls. Reversible.
- **C2**: Local process execution, file writes, or branch operations. Requires confirmation for destructive forms.
- **C3**: External API dispatch (Claude, Gemini, OpenRouter). Billed. Requires routing policy check.
- **C4**: Long-running or multi-hop agent chains. Fleet-scale. Requires governance approval.

---

## Related

- `CHROMATIC_COMMAND_LANGUAGE.md` — taxonomy and grammar
- `CHROMATIC_DICTIONARY.md` — full term definitions
- `AGENT_CONTROL_LOOP.md` — dispatch protocol
