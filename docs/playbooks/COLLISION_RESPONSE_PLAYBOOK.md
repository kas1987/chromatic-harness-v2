# Collision Response Playbook

## Trigger
Use this playbook when a lease request, queue claim, file edit, or state mutation collides with active work.

## Classification

| Class | Meaning | Response |
|---|---|---|
| Queue Collision | Two agents claim same task | First valid lease wins; second requeue |
| File Collision | Overlapping file/path mutation | Deny later lease |
| State Collision | Shared state mutation overlap | Halt and escalate |
| Stale Collision | Existing lease expired or heartbeat missing | Run stale recovery |
| Deadlock | Agents waiting on each other | Escalate to deadlock detector |

## Response Steps

1. Halt second mutation.
2. Record collision event.
3. Notify orchestrator.
4. Preserve both manifests.
5. Determine winner by active lease timestamp and validity.
6. Requeue or reroute losing task.
7. Open incident if collision was not safely prevented.

## Incident Template

```md
# Collision Incident

## Trigger

## Agents Involved

## Resources

## Active Lease

## Rejected Lease

## Impact

## Recovery Action

## Follow-up Prevention
```
