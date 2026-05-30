# Wiki EPIC-0001 ↔ Harness tracking (WK-002..WK-020)

> **Bead:** `chromatic-harness-v2-l8z`  
> **Wiki:** [kas1987/chromatic-wiki](https://github.com/kas1987/chromatic-wiki) — EPIC-0001 (issue #13)  
> **Harness source of truth:** Dolt/beads — not Wiki issues, not `.beads/issues.jsonl` export.

Machine-readable map: `config/wiki_harness_sync.yaml`  
Drift check: `python scripts/check_wiki_harness_sync.py`

---

## Important: WK ≠ ROUTE

Wiki **WK-** tasks are Knowledge OS backlog items (canon, taxonomy, research).  
Harness **ROUTE-** tasks are router/pre-session validation beads (`15x.*`).

Do **not** equate `WK-00N` with `ROUTE-00N` by number alone. Cross-links are in the table below.

---

## ROUTE ↔ Harness beads (router validation)

| ROUTE | Harness bead | Status (harness) | Primary tests / artifacts |
|-------|--------------|------------------|---------------------------|
| ROUTE-001 | `chromatic-harness-v2-15x.1` | closed | `tests/test_context_detector.py` |
| ROUTE-002 | `chromatic-harness-v2-15x.2` | closed | `tests/fixtures/complexity_cases.yaml` |
| ROUTE-003 | `chromatic-harness-v2-15x.3` | closed | `tests/test_provider_matrix.py` |
| ROUTE-004 | `chromatic-harness-v2-15x.4` | **open** | remote Ollama probe |
| ROUTE-005 | `chromatic-harness-v2-15x.5` | closed | `tests/test_openrouter_broker_policy.py` |
| ROUTE-006 | `chromatic-harness-v2-15x.6` | closed | privacy gate tests |
| ROUTE-007 | `chromatic-harness-v2-15x.7` | closed | `scripts/pre_session_manifest.py` |
| ROUTE-008 | `chromatic-harness-v2-15x.8` | closed | `tests/test_audit_mcp_context.py` |

Epics: `chromatic-harness-v2-gh1` (P1), `chromatic-harness-v2-uum` (P2).

---

## WK ↔ Harness cross-reference (EPIC-0001)

| WK | GH # | Wiki title (short) | Harness beads / ROUTE | Harness artifacts | Wiki status |
|----|-----:|--------------------|------------------------|-------------------|-------------|
| WK-002 | 2 | Knowledge intake & promotion framework | `l8z`, intake PDR | `auto_intake.py`, PDR §4–9 | open |
| WK-003 | 3 | Public AI wiki standards research | — | — | open |
| WK-004 | 4 | Agent architect knowledge taxonomy | — | `docs/beads/` | open |
| WK-005 | 5 | Canon vs non-canon standard | `ar7` (WIKI-005) | `promote_to_wiki.py`, canon checklist | open |
| WK-006 | 6 | Knowledge promotion pipeline | `ar7` (WIKI-004) | `harvest_rigs.py`, `sync_wiki_mirror.py` | open |
| WK-007 | 7 | Agent context consumption rules | ROUTE-007,008; `e0n` closed | CRG, `AGENT_ANTIPATTERNS.md`, MCP audit | open |
| WK-008 | 8 | Claude certified architect guide | — | research | open |
| WK-009 | 9 | Claude Code patterns | — | `.claude/workflows/` lite | open |
| WK-010 | 10 | OpenAI agent design patterns | — | research | open |
| WK-011 | 11 | Knowledge quality scorecard | — | promote confidence gates | open |
| WK-012 | 12 | Knowledge deprecation process | — | — | open |
| WK-013 | 13 | Repository folder architecture | `j9o` closed | `REPO_AND_RIG_INVENTORY.md` | open |
| WK-014 | 14 | Knowledge object schema | — | `BEADS_OBJECT_MODEL.md` | open |
| WK-015 | 15 | Agent architect competency matrix | — | — | open |
| WK-016 | 16 | Model routing knowledge base | ROUTE-001..006; `gh1` | `ROUTER_VALIDATION_BEADS.md`, router/ | open |
| WK-017 | 17 | Chromatic canon registry | `ar7` (WIKI-005/006) | Wiki `00_CANON/registry.yaml` | open |
| WK-018 | 18 | Research intake workflow | intake queue | `07_LOGS_AND_AUDIT/intake_queue.jsonl` | open |
| WK-019 | 19 | Source reliability framework | — | PDR §11 source tiers | open |
| WK-020 | 20 | Agent architect learning path | — | playbooks, `.agents/learnings/` | open |

**WK-001** (GH #1, wiki operating model) is parent context — tracked under Wiki v0.1 epic `chromatic-harness-v2-ar7`.

---

## Sync workflow

1. Change harness → update `config/wiki_harness_sync.yaml` + this doc.
2. Run `python scripts/check_wiki_harness_sync.py` (local bead status).
3. Optional: `python scripts/check_wiki_harness_sync.py --github` (Wiki issue states via `gh`).
4. Mirror approved governance: `python scripts/sync_wiki_mirror.py --execute`.
5. Close Wiki GH issues only after human review — harness bead closure does not auto-close Wiki.

---

## Related

- [ROUTER_VALIDATION_BEADS.md](ROUTER_VALIDATION_BEADS.md)
- [WIKI_V01_BEADS.md](WIKI_V01_BEADS.md)
- [PDR_CHROMATIC_BEADS_OPENROUTER_PIPELINE.md](../pdr/PDR_CHROMATIC_BEADS_OPENROUTER_PIPELINE.md)
- [WIKI_REPO_AND_PROMOTION.md](../WIKI_REPO_AND_PROMOTION.md)
