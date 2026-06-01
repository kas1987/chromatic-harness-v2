# Error Remediation Queue

This queue is generated from medium/high/critical Harness events. Do not treat the raw error log as a task list; use this queue for agent dispatch.

| ID | Status | Priority | Source Event | Category | Severity | Suggested Owner | Task | Definition of Done |
|---|---|---:|---|---|---|---|---|---|
| ERR-BOOTSTRAP-001 | done | P2 | evt_bootstrap | manual_note | info | Scribe | Initialize queue | Queue exists and is referenced by router |
