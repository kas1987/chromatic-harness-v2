# Chromatic Workflow Runtime

## Purpose

The workflow runtime converts high-level user commands into bounded, scored, verifiable agent work.

## Runtime Loop

```text
Observe -> Plan -> Build Task Graph -> Score -> Dispatch -> Verify -> Log -> Queue Next
```

## Runtime Rules

1. Read only the minimum project state needed.
2. Convert vague intent into bounded tasks.
3. Build or update a task graph before dispatch.
4. Score confidence and risk before mutation.
5. Route work by model strength.
6. Verify before marking work done.
7. Log every run.
8. Queue the next safest action.

## Stop Conditions

Stop immediately if:

- required context is missing
- task expands outside scope
- confidence drops below 60
- destructive action is needed
- permission gate blocks the action
- test failures repeat twice
- model begins broad repo wandering
