# Promote Playbook

Operating level: **promote** (harness → durable-canon wiki).

Operationalizes the promotion half of the knowledge flywheel. The *cadence* (when/what
each family repo promotes, cross-repo dedup) is specified in
[WIKI_CONVERGENCE_CADENCE.md](../WIKI_CONVERGENCE_CADENCE.md); this playbook is the
step-by-step run.

## When
- After an epic `/post-mortem` (`--cadence epic-close`).
- On the weekly sweep (`--cadence weekly`).
- See the cadence matrix for per-repo triggers and confidence gates.

## Steps
1. Consolidate learnings: `python scripts/harvest_rigs.py --execute`.
2. List candidates: `python scripts/promote_to_wiki.py --dry-run` (≥ confidence gate).
3. Human review — approve via the candidate staging guard (`.agents/candidates/<slug>.md`,
   `status: approved`).
4. Promote: `python scripts/promote_to_wiki.py --execute --repo-id <repo> --cadence <trigger>`.
   - Cross-repo dedup: the wiki `02_LEARNINGS/_promotion_index.json` ledger skips a
     learning already promoted by any family repo (counted as `deduped`).
5. Open a PR on `chromatic-wiki` (CANON_PR_CHECKLIST → `registry.yaml`).

## Guardrails
- Nothing reaches canon without review (`forbidden: durable_canon_without_review`).
- The wiki is a sink; never promote *from* it.
- Provenance (`repo_id`, `cadence`, `promoted_at`) is recorded in the ledger for every
  promoted entry.

## Related
- [WIKI_CONVERGENCE_CADENCE.md](../WIKI_CONVERGENCE_CADENCE.md)
- [WIKI_REPO_AND_PROMOTION.md](../WIKI_REPO_AND_PROMOTION.md)
- `scripts/promote_to_wiki.py`, `scripts/sync_wiki_mirror.py`
