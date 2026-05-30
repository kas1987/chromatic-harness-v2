# Harness Boot Context

> Generated snapshot for a clean Chromatic Harness v2 session. This file is operational context, not permanent canon.

## Session Status

| Field | Value |
|---|---|
| Generated At | {{generated_at}} |
| Rebuild Mode | {{mode}} |
| Repo Root | {{repo_root}} |
| Context Risk | {{risk_level}} |

## Active Mission

{{active_mission}}

## Git State

```text
Branch: {{git_branch}}
Status:
{{git_status}}
```

## Active Handoff

```text
Latest pointer: {{latest_handoff_pointer}}
Handoff path: {{handoff_path}}
```

## Active Beads

```text
{{beads_summary}}
```

## Allowed Pre-Session Context

### Always Load

{{always_load}}

### Load Only If Relevant

{{load_if_relevant}}

### Never Auto-Load

{{never_auto_load}}

## Context Audit Findings

{{audit_findings}}

## Next Action

{{next_action}}

## Stop Conditions

Stop and rebuild again if:

- Context reaches 75%+.
- Required task context is missing.
- Agent starts reading unrelated logs, archives, or old handoffs.
- Active bead/mission is unclear.
- A destructive action is required.

## Reminder

Do not use this file as a replacement for beads, git, or canon. Use it as a compact entry packet for the next bounded session.
