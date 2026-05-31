# GO-Mode Session Startup SOP
Run this read sequence at the start of every session before taking any action:

1. `cat 00_META/REPO_OPERATING_CONTRACT.md`   — scope and constraints
2. `bd ready` — current unblocked work queue
3. `cat 01_STATE/SPRINT_STATE.md`             — current objective
4. `cat 01_STATE/AGENT_HANDOFF_QUEUE.md`      — queued tasks
5. `cat 01_STATE/DECISION_LOG.md`             — recent decisions (avoid re-deciding)
6. Apply P1-P4 gate (SessionStart hook fires automatically)

Then claim the top bead and proceed.

## Telemetry
After each session, append a record to `05_REPORTS/telemetry.jsonl`:
`python scripts/hooks/append_session_telemetry.py`
