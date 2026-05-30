# P3 Automation Backlog (deferred)

> Start after **~1 week** stable ops on Phases 1–4. Track in beads epic `chromatic-harness-v2-7d2`.

| Bead | Item | Automation approach |
|------|------|---------------------|
| `chromatic-harness-v2-7d2.6` | Autonomy L0–L5 | Config + gate hooks in runtime; not cron |
| `chromatic-harness-v2-7d2.5` | Playbook evolution | Batch read `07_LOGS_AND_AUDIT/decisions/` → suggested doc PRs |
| `chromatic-harness-v2-7d2.7` | Full MCP ecosystem | Wire reference servers; keep `harness_dev` profile lean |

Do not schedule until [HARNESS_AUTOMATION_RUNBOOK.md](HARNESS_AUTOMATION_RUNBOOK.md) intake + smoke tasks run reliably.
