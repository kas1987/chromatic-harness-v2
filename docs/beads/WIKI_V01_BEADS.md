# Wiki v0.1 — Beads backlog

Epic and children for bootstrapping `kas1987/-Chromatic_Wiki`.

## Epic

**Title:** Wiki v0.1 — scaffold, mirror, first canon  
**Type:** epic  
**Priority:** P1

## Children

| ID | Title | Lane | Acceptance |
|----|-------|------|------------|
| WIKI-001 | Initial scaffold committed and pushed | agent | README, manifest, folder layout on `main` |
| WIKI-002 | Mirror harness governance + antipatterns | agent | `sync_wiki_mirror.py --execute`; files under `03_GOVERNANCE/`, `04_ANTIPATTERNS/` |
| WIKI-003 | Mirror harness playbooks (if present) | agent | `01_PLAYBOOKS/harness/` populated or documented empty |
| WIKI-004 | Promote first 5 learnings (confidence ≥ 0.75) | agent | `promote_to_wiki.py --execute`; PR on Wiki |
| WIKI-005 | Canon: ACTIVITY_LOG_AND_DUAL_BACKLOG | human | registry entry + PR checklist complete |
| WIKI-006 | Canon: AGENT_ANTIPATTERNS mirror | human | registry entry after review |
| WIKI-007 | Optional repo rename `chromatic-wiki` | human | GitHub rename + update `CHROMATIC_WIKI_ROOT` docs |

## Commands

```bash
bd create "Wiki v0.1 — scaffold, mirror, first canon" --type epic --priority p1
# Then create children and --parent <epic-id>
python scripts/sync_wiki_mirror.py --execute
python scripts/promote_to_wiki.py --execute
```
