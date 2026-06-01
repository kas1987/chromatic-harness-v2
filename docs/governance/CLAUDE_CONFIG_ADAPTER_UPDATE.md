# Claude Config Adapter Update

## Purpose

Update `claude-config` so it remains useful without competing with Harness v2.

## Core Rule

Claude config may provide shortcuts, commands, context, and routing hints. It must not own execution decisions.

## Allowed

- `/go` as a launcher into Harness v2 GO-mode.
- `/audit` as a launcher into health/readiness/drift checks.
- `/status` as a read-only summary.
- `/ship` as a wrapper around `scripts/workflow_git.py`.
- `/recover` as a wrapper around lease and collision diagnostics.
- Model routing hints when they defer to Harness v2 router locally.

## Forbidden

- Independent queue selection.
- Independent confidence scoring.
- Independent shipping logic.
- Bypassing verifier approval.
- Ignoring leases/collision gates.
- Direct merge authority.
- Silent subagent dispatch outside Harness logs.

## Required README Notice

```md
## Authority Notice

This repo is an adapter/config layer. Runtime execution, queue dispatch, confidence gates, verifier gates, collision control, and shipping authority live in `kas1987/chromatic-harness-v2`.
```
