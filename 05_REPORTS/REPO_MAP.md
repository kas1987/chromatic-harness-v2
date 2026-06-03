# Chromatic Harness v2 — Repo Map

> **Structural source of truth:** [`CHROMATIC_TREES.md`](../CHROMATIC_TREES.md) (operation→file map, legacy paths).
> This diagram is a high-level overview only.

```mermaid
graph TD
    ROOT[chromatic-harness-v2]
    ROOT --> SOT[00_SOURCE_OF_TRUTH\nManifest · Governance]
    ROOT --> META[00_META\nOperating Contract]
    ROOT --> PROTO[01_PROTOCOLS\nSchemas · BEADS · CMP]
    ROOT --> STATE[01_STATE\nSprint · Leases]
    ROOT --> RUNTIME[02_RUNTIME\nRouter · Engines · Magnets]
    ROOT --> PB[04_PLAYBOOKS\nRole Runbooks]
    ROOT --> REPORTS[05_REPORTS\nKPIs · Scorecard]
    ROOT --> LOGS[07_LOGS_AND_AUDIT\nAudit · Review Intake]
    ROOT --> PDR[08_PDRS\nDesign Records]
    ROOT --> HANDOFFS[12_HANDOFFS\nSession Handoffs]
    ROOT --> DOCS[docs/\nGovernance · Research · Retros]
    ROOT --> SCRIPTS[scripts/\nAutomation · Hooks]
    ROOT --> CLAUDE[.claude/\nSettings · Workflows]

    RUNTIME --> ROUTER[router/\ngate.py · model routing]
    RUNTIME --> ENGINES[runtime-engines/\nroach-pi]
    RUNTIME --> MAGNETS[magnets/\nClosureMagnet · ContextPressure]

    LOGS --> REVIEW[review_intake/\nfindings · queue · dispatch]

    STATE --> LEASES[leases/\ncollision ledger]
```

## Review intake (harness-native paths)

| Artifact | Path |
|----------|------|
| Findings JSONL | `07_LOGS_AND_AUDIT/review_intake/findings.jsonl` |
| Work queue | `07_LOGS_AND_AUDIT/review_intake/queue.json` |
| State | `07_LOGS_AND_AUDIT/review_intake/state.json` |
| PDR | `08_PDRS/PDR_REVIEW_INTAKE_2026-06-01.md` |

See [`07_LOGS_AND_AUDIT/audits/repo_reorg_audit_2026-06-01.md`](../07_LOGS_AND_AUDIT/audits/repo_reorg_audit_2026-06-01.md) for zip→harness path mapping.
