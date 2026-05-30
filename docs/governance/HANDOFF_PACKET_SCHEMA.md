# Handoff Packet Schema

## Purpose

Prevent workflow phases from passing raw full output into later phases.

## Required Packet

```json
{
  "objective": "string",
  "decision": "string",
  "summary": "string, max 500 words",
  "evidence_refs": ["string"],
  "files_touched": ["string"],
  "risks": ["string"],
  "blockers": ["string"],
  "next_action": "string",
  "confidence": 0,
  "budget_used": {
    "tool_calls": 0,
    "files_read": 0,
    "approx_tokens": 0
  }
}
```

## Rules

- Packet summary must be under 500 words.
- Raw logs are forbidden.
- Full transcript excerpts are forbidden unless explicitly approved.
- Evidence should be referenced by path, line range, commit, or file name instead of pasted wholesale.
- Later phases receive only the packet, not the entire prior conversation.
