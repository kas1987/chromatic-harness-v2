# Downloads ingest audit — 2026-05-30

Source folder: `C:\Users\kas41\Downloads` (files from 2026-05-28–29).

## Ingested into repo

| Download | Repo paths | Beads |
|----------|------------|-------|
| `chv2_context_rebuild_pack.zip` | `docs/pdr/PDR-CHV2-002_*`, `docs/governance/CONTEXT_REBUILD_POLICY.md`, `scripts/context_*.py`, `scripts/new_session_bootstrap.py`, `docs/beads/CONTEXT_REBUILD_BEADS.md`, `.agents/context/` | Epic `chromatic-harness-v2-745` + CTX-001..004 |
| `claude-token-governance-pdr.zip` | `docs/pdr/PDR_CLAUDE_WORKFLOW_TOKEN_GOVERNANCE.md`, `docs/governance/00_WORKFLOW_GOVERNANCE.md`, `WORKFLOW_BUDGET_CONTRACT.md`, `docs/workflows/patches/`, handoffs → `12_HANDOFFS/sessions/` | Epic `chromatic-harness-v2-dcm`, `chromatic-harness-v2-5be` |
| `PDR_CHROMATIC_BEADS_OPENROUTER_PIPELINE.md` | `docs/pdr/PDR_CHROMATIC_BEADS_OPENROUTER_PIPELINE.md` | `chromatic-harness-v2-l8z` (wiki sync) |
| `PDR-API-ROUTING-OPENHUMAN.md` | already in `docs/pdr/` | `chromatic-harness-v2-a71` |

## Already ingressed (no new beads)

- `chromatic-dynamic-workflow-runtime.zip` → `docs/workflows/`, PDR-DYNAMIC-WORKFLOW-RUNTIME-001
- `sonnet-kimi-governance.zip` → PDR-GOV-SONNET-KIMI-001
- `chromatic_harness_v2_pdr_package.zip` → `08_PDRS/`, magnets, playbooks
- `chv2_pre_session_pack.zip` → `docs/governance/PRE_SESSION_*`, `docs/BEADS_OBJECT_MODEL.md`

## Deferred / non-work

- `usage-events-2026-05-28*.csv` — billing analysis only
- `ChatGPT Image *.png` — assets
- Extracted duplicate folders under Downloads — safe to delete locally

## Intake queue

- Ran `scripts/dedupe_intake_queue.py` — **64** test/closure duplicates marked `skipped`.

## Chromatic Wiki (separate repo)

21 open GitHub issues on `kas1987/-Chromatic_Wiki` — tracked via bead `chromatic-harness-v2-l8z`.
