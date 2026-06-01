# Agent Usage Guide

## Default Agent Rule

When an agent encounters an error, it must not silently fix and forget. It should either:

1. Log the event.
2. Link the fix to the event.
3. Add a learning if the pattern is repeated or structural.
4. Escalate if severity is high or critical.

## Agent Error Response Format

```md
## Error Captured

- Event ID:
- Severity:
- Category:
- Files touched:
- Command/tool:
- Immediate action:
- Next action:
```

## Agent Collision Rule

If the agent detects another writer on the same file, it must stop and create a collision record.

## Agent Learning Rule

Agents may propose learnings, but learnings must cite event IDs or direct evidence.
