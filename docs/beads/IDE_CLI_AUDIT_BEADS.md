# IDE / CLI Audit Beads Backlog

Use these as seed beads in `bd`.

## AUDIT-001: Add daily harness audit script

Priority: p1  
Owner: Auditor  
Done when:

- `scripts/daily_harness_audit.py` exists
- audit generates JSON and Markdown outputs
- audit runs from repo root

## AUDIT-002: Add IDE parity audit script

Priority: p1  
Owner: Cartographer  
Done when:

- `scripts/audit_ide_parity.py` exists
- Cursor, Claude, VS Code, and CLI wrappers are inspected
- missing wrappers are reported

## AUDIT-003: Add instruction drift audit

Priority: p1  
Owner: Sentinel  
Done when:

- `scripts/audit_instruction_drift.py` exists
- duplicated governance blocks are detected
- conflicting rules are flagged

## AUDIT-004: Add Cursor harness audit rule

Priority: p2  
Owner: Janitor  
Done when:

- `.cursor/rules/harness-audit.mdc` exists
- Cursor rule points to repo-owned scripts

## AUDIT-005: Add VS Code harness tasks

Priority: p2  
Owner: Janitor  
Done when:

- `.vscode/tasks.json` exposes bootstrap, audit, trim, rebuild tasks

## AUDIT-006: Add daily audit runbook

Priority: p2  
Owner: Archivist  
Done when:

- `docs/governance/DAILY_AUDIT_RUNBOOK.md` exists
- daily review flow is documented

## AUDIT-007: Add IDE/CLI parity policy

Priority: p2  
Owner: Archivist  
Done when:

- `docs/governance/IDE_CLI_PARITY_POLICY.md` exists
- repo-owned policy principle is documented

## AUDIT-008: Add optional GitHub Actions audit workflow

Priority: p3  
Owner: Auditor  
Done when:

- `.github/workflows/harness-daily-audit.yml` exists
- workflow runs without requiring secrets
