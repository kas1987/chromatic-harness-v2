# Agent Handoff: Sentinel - Patch Review Finding

## Mission
Patch a ready review finding after the dispatcher assigns it.

## Required Inputs
- Queue item ID
- Source finding ID
- PR link/comment link
- Allowed files
- Acceptance checks

## Required Steps

1. Acquire PR branch lock.
2. Read the source finding and linked PR context.
3. Edit only allowed files.
4. Run acceptance checks.
5. Generate resolution comment.
6. Release PR branch lock.
7. Update queue and resolution log.

## Stop Conditions
- Lock cannot be acquired.
- Fix requires files outside allowed scope.
- Reviewer intent is unclear.
- Security/architecture human gate is present.
- Tests fail outside touched scope.
