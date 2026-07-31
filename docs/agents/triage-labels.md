# Triage labels

The `mattpocock-triage` skill speaks in five canonical triage roles. This file maps those roles to the harness v2 vocabulary.

| Role in mattpocock/skills | Harness v2 label / state | Meaning |
| -------------------------- | ------------------------ | ------- |
| `needs-triage`             | `needs-triage`             | Agent lead or maintainer still needs to evaluate the issue. |
| `needs-info`               | `needs-info`               | Blocked waiting on reporter/mission packet for more information. |
| `ready-for-agent`          | `ready-for-agent`          | Fully specified, claimed, and ready for agent implementation. |
| `ready-for-human`          | `ready-for-human`          | Requires human decision or execution (e.g., secret rotation, infra change). |
| `wontfix`                  | `wontfix`                  | Explicitly out of scope or superseded. |

In beads, triage state is expressed through the issue status (`open`, `in_progress`, `blocked`, `closed`, `deferred`) and through `bd update <id> --notes=` commentary. When `mattpocock-triage` asks to "apply a label", update the issue notes accordingly and, where beads supports labels, set the matching label string.
