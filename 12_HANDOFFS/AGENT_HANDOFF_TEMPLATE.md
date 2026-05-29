# Agent Handoff — {{MISSION_ID}}

**Date:** {{DATE}}  
**Agent:** {{AGENT}} (Claude / Pi / Codex / other)  
**Branch:** {{BRANCH}}  
**Last commit:** {{LAST_COMMIT}}

---

## Directive summary

{{DIRECTIVE_SUMMARY}}

---

## Context snapshot

| Field | Value |
|-------|-------|
| Mission ID | {{MISSION_ID}} |
| Objective | {{OBJECTIVE}} |
| Autonomy level | {{AUTONOMY_LEVEL}} |
| Composite score | {{COMPOSITE_SCORE}} |
| Decision | {{DECISION}} |

---

## What was done this session

- {{DONE_1}}
- {{DONE_2}}
- {{DONE_3}}

---

## Verification

| Gate | Status |
|------|--------|
| Tests | {{TEST_STATUS}} |
| Lint | {{LINT_STATUS}} |
| Beads updated | {{BEADS_STATUS}} |
| Pushed to origin | {{PUSH_STATUS}} |

---

## Open work (beads)

| ID | Title | Priority |
|----|-------|----------|
| {{BEAD_ID_1}} | {{BEAD_TITLE_1}} | {{PRIORITY_1}} |

```bash
bd ready
bd show {{BEAD_ID_1}}
```

---

## Next session goals

1. {{NEXT_GOAL_1}}
2. {{NEXT_GOAL_2}}
3. {{NEXT_GOAL_3}}

---

## Recommended next command

```bash
{{NEXT_COMMAND}}
```

---

## Risks / do not forget

- {{RISK_1}}
- {{RISK_2}}

---

## Audit reference

- Handoff JSON: `.agents/handoffs/latest.json`
- RPI packet: `.agents/rpi/execution-packet.json` (if applicable)
- Chronicle: `.agents/chronicle/events.jsonl`
