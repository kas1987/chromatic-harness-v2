# Downloads audit — 2026-05-29

Source: `C:\Users\kas41\Downloads` (scan of zips + `.md` PDRs).

Prior ingest log: [DOWNLOADS_INGEST_20260530.md](DOWNLOADS_INGEST_20260530.md).

## Ingested 2026-05-29 (`chv2_ide_cli_audit_pack.zip`)

| Artifact | Repo path |
|----------|-----------|
| PDR | `docs/pdr/PDR-CHV2-003_IDE_CLI_AUDIT_AND_DAILY_MONITORING.md` |
| Scripts | `scripts/daily_harness_audit.py`, `audit_ide_parity.py`, `audit_instruction_drift.py` |
| Governance | `docs/governance/IDE_CLI_PARITY_POLICY.md`, `DAILY_AUDIT_RUNBOOK.md` |
| Beads seed | `docs/beads/IDE_CLI_AUDIT_BEADS.md` |
| Cursor / VS Code / CI | `.cursor/rules/harness-audit.mdc`, `.vscode/tasks.json`, `.github/workflows/harness-daily-audit.yml` |

Merged with existing `context_trim_audit`, `validate_instruction_governance`, `validate_governance_stack`. Beads epic **CHV2-003** filed in bd.

## Already ingested / covered (no action)

| Download | Repo / beads |
|----------|----------------|
| `chv2_context_rebuild_pack.zip` | Ingested — epic `745` closed |
| `claude-token-governance-pdr.zip` | Ingested — `dcm`, `5be` closed |
| `PDR_CHROMATIC_BEADS_OPENROUTER_PIPELINE.md` | `docs/pdr/` — bead `l8z` |
| `PDR-API-ROUTING-OPENHUMAN.md` | `docs/pdr/` — bead `a71` |
| `chv2_pre_session_pack.zip` | PRE_SESSION docs, CHV2-001 |
| `chromatic-dynamic-workflow-runtime.zip` | `PDR-DYNAMIC-WORKFLOW-RUNTIME-001`, workflows |
| `sonnet-kimi-governance.zip` | `PDR-GOV-SONNET-KIMI-001` |
| `chromatic_harness_v2_pdr_package.zip` | `08_PDRS/`, playbooks, magnets |

## Other rigs / projects (do not ingest into harness-v2)

| Download | Route |
|----------|--------|
| `chromatic_design_studios_pdr_pack.zip` | `C:\Users\kas41\chromatic-design-studios` scaffold PDR |
| `chromatic-design-studios-pdr.zip` | Same rig — master PDR + backlog |
| `chromatic-design-studios.zip` | Small asset/archive |
| `chromatic-youtube-to-pdr.zip` | Standalone pipeline repo (not harness core) |

## Non-work (ignore for beads)

- `usage-events-2026-05-28*.csv` — billing only
- `ChatGPT Image *.png`, `AI Eco.png`, 3d/front-end assets — media
- `openart-download.zip` (~1.1 GB), `*.mp4` — creative assets
- `XCOM2_*`, `SteamSetup.exe`, `NVIDIA_app_*.exe` — installers/games
- `openart-results-aa.json`, `openart-filelist.txt` — misc
- `Nice to meet you.eml`, `2025 Resume - KS.docx` — personal

## Recommended next command (if ingesting CHV2-003)

```powershell
Expand-Archive -Force "$env:USERPROFILE\Downloads\chv2_ide_cli_audit_pack.zip" -DestinationPath "$env:TEMP\chv2_ide_cli_audit_pack"
# Then merge into repo (dedupe with validate_instruction_governance + context_trim_audit)
bd create "Epic: CHV2-003 IDE/CLI audit and daily monitoring" --type epic
```
