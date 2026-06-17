# Review and Implementation Playbook

## Review Checklist

1. Confirm mission level.
2. Confirm objective clarity.
3. Confirm scope and out-of-scope.
4. Confirm allowed and forbidden files.
5. Confirm acceptance criteria.
6. Confirm tool budget.
7. Confirm risk and rollback plan.
8. Confirm validation strategy.
9. Confirm approval requirements.

## Implementation Rules

- Implement the smallest safe change.
- Do not combine unrelated fixes.
- Do not silently expand scope.
- Do not skip tests because the change looks simple.
- Do not close without evidence.

## Auditor Rules

The auditor must verify:

- The diff matches the packet.
- The acceptance criteria were met.
- Validation evidence is present.
- No forbidden files were changed.
- No new unmanaged risk was introduced.
- Logs and next task were updated.
