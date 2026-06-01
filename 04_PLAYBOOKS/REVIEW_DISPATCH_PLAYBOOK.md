# Review Dispatch Playbook

## Purpose

Route queued review findings to the correct agent or subagent with bounded scope.

## Dispatch Requirements

Every dispatch must include:

- task ID
- source finding ID
- PR link/comment link
- owner agent
- allowed files
- forbidden files
- acceptance checks
- confidence score
- risk level
- stop conditions

## Agent Routing

| Finding Type | Agent |
|---|---|
| security | Sentinel |
| test_failure | Auditor |
| lint_style | Janitor |
| docs | Archivist |
| architecture | Archivist / Auditor |
| bug_fix | Sentinel |
| repo_hygiene | Janitor |
| unclear | Auditor |

## Dispatch Rule

Only dispatch `ready` items unless the user explicitly requests blocked/planned review.

## Stop Conditions

- Confidence below 75 for mutation work.
- Allowed files are empty for code mutation.
- Human gate required.
- PR branch already has an active mutation lock.
