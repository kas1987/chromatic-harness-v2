# Observability Playbook

## 1. Purpose

This playbook governs how Chromatic Harness captures, classifies, routes, reviews, and learns from errors and operational events across IDEs, terminals, agents, scripts, and repos.

## 2. Scope

### In Scope

- Terminal command failures
- IDE task failures
- Agent execution failures
- File collisions
- Git state errors
- Test/build/lint failures
- Tool-call failures
- Context drift
- Scope breaches
- Secret exposure events
- Repeated error patterns

### Out of Scope

- Full enterprise APM implementation
- Unbounded telemetry collection
- Raw secret/environment capture
- Automatic destructive recovery

## 3. Standard Loop

```text
Observe -> Redact -> Normalize -> Classify -> Persist -> Route -> Review -> Learn
```

## 4. Required Fields

Every event must include:

- `event_id`
- `timestamp`
- `event_type`
- `severity`
- `category`
- `message`
- `source.surface`
- `status`

## 5. Routing Rules

| Severity | Route |
|---|---|
| info | Append to log |
| low | Append to log, optional learning |
| medium | Append to log and consider queue item |
| high | Halt affected workflow, create queue item or incident |
| critical | Open incident and require human review |

## 6. Collision Rule

If multiple active writers touch the same file:

1. Stop writes to the file.
2. Record collision.
3. Assign one resolver.
4. Preserve evidence.
5. Update learning after resolution.

## 7. Retry Rule

Retry only once unless the failure mode is understood.

Never retry blindly.

## 8. Secret Rule

Never log raw values matching likely tokens, API keys, private keys, passwords, cookies, or authorization headers.

If a secret appears in an event:

1. Redact it.
2. Mark `redacted=true`.
3. If exposure occurred in a committed file or shared log, create a critical incident.

## 9. Learning Rule

A learning must include:

- Evidence event IDs
- What happened
- Why it happened
- Prevention rule
- Playbook or script update if needed

## 10. Quality Gate

Before closing an error-driven task:

- [ ] Event is logged
- [ ] Severity and category are correct
- [ ] Fix is linked when applicable
- [ ] Learning is added if repeated or structural
- [ ] Incident is opened if critical
- [ ] Queue is updated if follow-up work remains
