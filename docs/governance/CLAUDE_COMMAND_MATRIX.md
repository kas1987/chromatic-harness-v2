# Claude Command Matrix

| Command | Purpose | Authority Source | Script / Artifact | Mutates State? | Required Gates | Status |
|---|---|---|---|---:|---|---|
| `/go` | Start highest-priority approved work | Queue + Orchestrator | bd queue, GO-mode router | Conditional | confidence, lease, verifier if T3+ | Allowed |
| `/audit` | Report harness health | Harness health / governance gates | `scripts/harness_health_check.py`, `release_readiness.py`, `drift_gate.py` | No by default | none for read-only | Allowed |
| `/status` | Summarize current harness state | Existing artifacts | reports, logs, queue | No | none | Allowed |
| `/ship` | Plan or execute shipping | `workflow_git.py` | `scripts/workflow_git.py` | Conditional | verifier, tests, collision, CI | Allowed |
| `/recover` | Inspect failures and stale leases | Recovery policy | `lease_manager.py`, logs | Inspect by default | human gate for mutation | Allowed |
| `/queue` | Show or import queue state | bd / GitHub issues | bd queue | Conditional | queue policy | Allowed |
| `/explain` | Explain artifacts for human | Existing artifacts | docs, reports, logs | No | none | Allowed |

## Forbidden Command Types

| Command Type | Reason |
|---|---|
| Direct merge command | Bypasses `workflow_git.py`, verifier, CI |
| Direct file mutation command | Bypasses lease and confidence gates |
| Direct queue rewrite command | Bypasses queue ownership |
| Autonomous hidden dispatch command | Creates invisible work |
| Confidence override command | Breaks governance scoring |
| Verifier bypass command | Removes independent review |
