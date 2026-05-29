# v2 Harness Consolidation — Beads Map (Close Loops First)

> **Epic:** `chromatic-harness-v2-h24` — v2 Harness consolidation — close loops first  
> **Principle:** Finish **intake → beads → GO → verify → closure → intake** before expanding surface area.

Research source: [CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md](./CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md)

---

## P0 — Close the core loop (do these first)

| Bead | Title | Delivers |
|------|-------|----------|
| `chromatic-harness-v2-8ua` | Define unified `intake_queue.jsonl` contract + docs | Single queue schema under `07_LOGS_AND_AUDIT/intake_queue.jsonl` |
| `chromatic-harness-v2-nev` | Route bead-intake hook to repo intake queue | `.beads/hooks/bead-intake.sh` writes to repo queue (not only `~/.claude`) |
| `chromatic-harness-v2-irm` | Closure feedback → intake queue | Session compact / closure magnet appends follow-up goals |
| `chromatic-harness-v2-4ie` | `auto_intake.py` queue drain → `bd create` / claim | `02_RUNTIME/intake/auto_intake.py` |
| `chromatic-harness-v2-1o2` | E2E validation script | `scripts/validate_intake_loop.py` — intake → bd → GO VERIFY |

**Dependency chain:** `8ua` → `nev` + `irm` → `4ie` → `1o2`

```text
Goal/hook/closure → intake_queue.jsonl → auto_intake → bd ready → workflow_go → verify → closure → queue
```

---

## P1 — Extend loop (blocked until P0 E2E passes)

| Bead | Title | Blocked by |
|------|-------|------------|
| `chromatic-harness-v2-6a4` | Inbox harness adapter → intake queue | `1o2` |
| `chromatic-harness-v2-rza` | Task-graph scout/builder/verifier roles | `1o2` |
| `chromatic-harness-v2-ms8` | Chromatic MCP server | `scripts/chromatic_mcp_server.py` + [CHROMATIC_MCP_SERVER.md](../CHROMATIC_MCP_SERVER.md) |

**Epic `chromatic-harness-v2-h24`:** P0 + P1 complete. P2 beads remain optional.

---

## P2 — Deferred until loop is stable

| Bead | Title |
|------|-------|
| ~~`chromatic-harness-v2-l3b`~~ | roach-pi submodule + hardened adapter — **done** (`.gitmodules`, loader, scope guards) |
| ~~`chromatic-harness-v2-chm`~~ | Two-log audit — **done** (`02_RUNTIME/audit/two_log.py`, mirrored from `append_run_log`) |
| ~~`chromatic-harness-v2-1z2`~~ | `harvest_rigs.py` — **done** (`02_RUNTIME/knowledge/harvest_rigs.py`, session handoff hook) |
| ~~`chromatic-harness-v2-knd`~~ | Self-heal band (50–69) → GO DEEP + re-decompose — **done** (`02_RUNTIME/workflows/self_heal.py`) |

---

## What we are NOT doing yet

- New harness repos or git submodules (except roach-pi P2 bead)
- Full AgentOps / Fusion Computer runtime dependencies
- Unbounded `/crank` or `GO SWARM` without approved task graph
- 15+ MCP plugins for daily dev (see [AGENT_ANTIPATTERNS.md](../AGENT_ANTIPATTERNS.md))

---

## Start work

```bash
bd ready                    # should surface chromatic-harness-v2-8ua when unblocked
python scripts/validate_intake_loop.py   # after P0 complete
```
