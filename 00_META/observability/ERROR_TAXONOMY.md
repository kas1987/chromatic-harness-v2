# Error Taxonomy

## Event Types

| Type | Meaning |
|---|---|
| info | Informational operational event |
| warning | Non-fatal warning |
| error | Failed operation |
| incident | Serious event requiring review |
| collision | Multi-writer file conflict |
| learning | Durable lesson or pattern |

## Severity

| Severity | Definition |
|---|---|
| info | No failure; useful context |
| low | Minor recoverable problem |
| medium | Work-blocking but contained issue |
| high | Risk to repo state, build state, or agent governance |
| critical | Secret exposure, data loss, destructive action, or severe governance breach |

## Categories

| Category | Description | Examples |
|---|---|---|
| tool_failure | Tool returned error or unavailable | CLI crash, API timeout |
| file_collision | Multiple sessions touched same file | Claude and Codex edit same file |
| test_failure | Validation failed | lint/test/build failure |
| dependency_error | Missing/broken dependency | missing package, version conflict |
| context_drift | Agent used stale/wrong context | old PDR, wrong branch |
| scope_breach | Agent exceeded allowed scope | edited forbidden file |
| secret_exposure | Sensitive value exposed | API key in log |
| loop_behavior | Unproductive repeated action | repeated searches, retries |
| model_misroute | Wrong model used | cheap model for architecture decision |
| playbook_gap | Governance missing | no rule for scenario |
| permission_error | Auth/access issue | denied write, missing token |
| git_state_error | Git working tree issue | dirty tree, merge conflict |
| environment_error | Local environment issue | missing Python, path problem |
| artifact_error | Output artifact bad/missing | zip invalid, doc missing |

## Status Values

| Status | Meaning |
|---|---|
| open | Needs attention |
| triaged | Classified, awaiting action |
| queued | Follow-up task exists |
| active | Being worked |
| resolved | Fixed or accepted |
| ignored | Logged but no action needed |
| escalated | Human/incident review needed |
