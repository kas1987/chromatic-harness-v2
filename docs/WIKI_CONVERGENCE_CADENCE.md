# Wiki Convergence Cadence (OMH-6)

Bead: `chromatic-harness-v2-w1bf.6` — *Multi-repo to wiki convergence cadence*.
Epic: `chromatic-harness-v2-w1bf` — Operating-Model Hardening (OMH).

Defines **when** and **what** each chromatic-family repo promotes into the shared
durable-canon wiki (`kas1987/chromatic-wiki`), and how the same learning surfacing in
more than one repo is **deduped** rather than duplicated. Wires
[`scripts/promote_to_wiki.py`](../scripts/promote_to_wiki.py) to that cadence.

Repo roles are the source of truth in
[`config/repo_role_registry.yaml`](../config/repo_role_registry.yaml); this doc maps
each role onto a promotion cadence. The wiki is `durable_canon` — it is the **sink**,
never a source.

## What each repo promotes

| Repo | Role | Promotes to wiki | Cadence trigger |
|------|------|------------------|-----------------|
| `chromatic-harness-v2` | execution_authority | reviewed `.agents/learnings/`, auto-turn calibration reports, approved governance docs | **epic-close** (after `/post-mortem`) + **weekly** sweep |
| `ChromaticSystems` | registry_and_skill_governance | skill catalog deltas, registry maps, cross-repo governance inventory | **on registry change** + weekly |
| `chromatic-stack` | local_service_substrate | local-infra runbooks, service-health learnings | **monthly** or on infra change |
| `claude-config` | claude_adapter_config (demoted) | model-routing hints, adapter conventions | **monthly**, low volume |
| `Chromatic_Brain` | legacy_brain_archive | migration extracts only (one-way drain) | **migration-only**, no recurring cadence |
| `chromatic-wiki` | durable_canon | — (sink) | n/a |

"Promote" everywhere means: stage a candidate, gate on confidence + human review, then
copy into the wiki `02_LEARNINGS/` (or the appropriate canon section) via
`promote_to_wiki.py --execute`. Nothing is auto-committed to canon without review
(`forbidden: durable_canon_without_review`).

## Cadence triggers

| Trigger | When | `--cadence` tag | Confidence gate |
|---------|------|-----------------|-----------------|
| `epic-close` | immediately after an epic's `/post-mortem` | `epic-close` | ≥ 0.80 |
| `weekly` | scheduled weekly sweep | `weekly` | ≥ 0.75 (default) |
| `monthly` | low-volume repos | `monthly` | ≥ 0.85 |
| `migration` | one-off legacy drain | `migration` | ≥ 0.90 + explicit review |
| `manual` | ad-hoc human run | `manual` | operator's choice |

Each run records its trigger so canon entries are traceable to a cadence, not just a
date:

```bash
# Harness, right after an epic post-mortem:
python scripts/promote_to_wiki.py --execute --cadence epic-close --min-confidence 0.80

# A sibling family repo's weekly sweep:
python scripts/promote_to_wiki.py --execute \
  --repo-id kas1987/ChromaticSystems --cadence weekly
```

## Cross-repo dedup

Two family repos can independently capture the *same* learning (e.g. a shared CI
gotcha). Without dedup, each would create a separate canon entry. The promotion ledger
prevents that:

- `promote_to_wiki.py` maintains `02_LEARNINGS/_promotion_index.json` in the wiki,
  keyed by a **content hash of the learning body** (frontmatter excluded — only the
  substance decides identity, so differing `promoted_from`/`promoted_by`/`date` do not
  defeat the match).
- Before promoting, the script checks the ledger: if the same body was already promoted
  by **any** repo and that entry still exists in the wiki, the promotion is **skipped**
  (counted as `deduped` in the run report) — even when the second repo would have used a
  different slug.
- On a real promotion the ledger records `{slug, repo_id, cadence, promoted_at}`, so
  canon carries provenance: which repo first contributed it and under which cadence.

This makes convergence **idempotent**: re-running any repo's cadence, or running two
repos that share a learning, converges to one canon entry instead of duplicates.

## The convergence loop

```text
per repo, on its cadence trigger:
  1. harvest_rigs.py --execute          # consolidate into .agents/learnings/
  2. promote_to_wiki.py --dry-run       # list candidates >= confidence gate
  3. human review (candidate staging guard: status: approved)
  4. promote_to_wiki.py --execute --repo-id <repo> --cadence <trigger>
       -> cross-repo ledger dedups; new entries tagged with provenance
  5. PR on chromatic-wiki (CANON_PR_CHECKLIST -> registry.yaml)
```

See also: [WIKI_REPO_AND_PROMOTION.md](WIKI_REPO_AND_PROMOTION.md) (repo split +
promotion workflow), [`config/wiki_harness_sync.yaml`](../config/wiki_harness_sync.yaml)
(mirror manifest).
