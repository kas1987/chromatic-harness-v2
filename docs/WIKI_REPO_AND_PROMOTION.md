# Chromatic Wiki — Separate Repo and Promotion

## Repos

| Repo | GitHub | Local (default) | Role |
|------|--------|-----------------|------|
| Harness v2 | `kas1987/chromatic-harness-v2` | `chromatic-harness-v2` | Execution, beads, automation, working `.agents/` knowledge |
| **Wiki** | `kas1987/chromatic-wiki` | `C:\Users\kas41\chromatic-wiki` | Durable playbooks, learnings, governance, canon registry |

PDR metadata: [PDR_CHROMATIC_BEADS_OPENROUTER_PIPELINE.md](pdr/PDR_CHROMATIC_BEADS_OPENROUTER_PIPELINE.md) lists the Wiki as the Chromatic Knowledge OS repo.

## What stays in harness vs Wiki

| Artifact | Harness | Wiki |
|----------|---------|------|
| Session logs, intake, two-log | Yes | No |
| `.agents/learnings/` (flywheel) | Yes | Promote when stable |
| `04_PLAYBOOKS/` (active) | Yes | Copy when reviewed |
| `docs/governance/` (draft) | Yes | Promote approved |
| Canon registry | Candidate only | `00_CANON/registry.yaml` |

## Scripts (harness)

| Script | Purpose |
|--------|---------|
| `sync_wiki_mirror.py` | Mirror governance, antipatterns, playbooks per Wiki `manifest.yaml` |
| `promote_to_wiki.py` | Copy `.agents/learnings/` (≥ min confidence) → Wiki `02_LEARNINGS/` |

```bash
python scripts/sync_wiki_mirror.py --dry-run
python scripts/sync_wiki_mirror.py --execute
python scripts/promote_to_wiki.py --dry-run
python scripts/promote_to_wiki.py --execute
```

## Promotion workflow

```text
0. sync_wiki_mirror.py --execute  # mirrored docs (edit in harness; re-sync)
1. harvest_rigs.py --execute      # consolidate rig learnings into .agents/learnings/
2. promote_to_wiki.py --dry-run   # list candidates ≥ min confidence
3. Human review                   # edit in Wiki or harness
4. promote_to_wiki.py --execute   # copy to Wiki 02_LEARNINGS/
5. PR on chromatic-wiki          # CANON_PR_CHECKLIST → registry.yaml
```

## Long-run loop post-mortem cadence

For long-running agent batches (for example 10-cycle delegation loops), run this sequence immediately after the batch:

```text
1. Capture loop artifacts and delegation observability
2. Write/append .agents/learnings entries from real failures and corrections
3. python scripts/harvest_rigs.py --execute
4. python scripts/promote_to_wiki.py --dry-run
5. python scripts/promote_to_wiki.py --execute
6. Open/update Wiki PR with incident notes and mitigation standards
```

Minimum data to preserve in each post-mortem learning:
- control-plane counts (cycles, delegate calls, delegate return codes)
- evidence-plane status (pickup correlation, reroute reason)
- shell/automation failure modes encountered in the run
- exact corrected command pattern used to recover

Canon: [00_CANON/CANON_PR_CHECKLIST.md](https://github.com/kas1987/chromatic-wiki/blob/main/00_CANON/CANON_PR_CHECKLIST.md)  
Beads: [beads/WIKI_V01_BEADS.md](beads/WIKI_V01_BEADS.md)  
Rename: [WIKI_REPO_RENAME.md](WIKI_REPO_RENAME.md) *(completed 2026-05-30)*

## Environment

Override Wiki path:

```powershell
$env:CHROMATIC_WIKI_ROOT = "C:\Users\kas41\chromatic-wiki"
```

## Clone Wiki (one-time)

```powershell
git clone https://github.com/kas1987/chromatic-wiki.git C:\Users\kas41\chromatic-wiki
```

## Related

- [KNOWLEDGE_HARVEST.md](KNOWLEDGE_HARVEST.md)
- [BEADS_OBJECT_MODEL.md](BEADS_OBJECT_MODEL.md) — `canon_candidate_bead`
- [REPO_AND_RIG_INVENTORY.md](REPO_AND_RIG_INVENTORY.md)
