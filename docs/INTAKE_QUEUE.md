# Intake Queue — Unified Close-Loop Contract

> **Bead:** `chromatic-harness-v2-8ua`  
> **Epic:** `chromatic-harness-v2-h24` (close loops first)

The intake queue is the **single append-only bus** between external producers (hooks, inbox, closure, humans) and `auto_intake.py`, which drains entries into **beads** (`bd create` / claim).

## File location

```text
07_LOGS_AND_AUDIT/intake_queue.jsonl   # runtime queue (git-tracked, may be empty)
01_PROTOCOLS/INTAKE/intake_queue.schema.json
02_RUNTIME/intake/queue.py             # read / append / validate helpers
```

Legacy hook path `~/.claude/.agents/intake/queue.jsonl` is **deprecated** — bead `chromatic-harness-v2-nev` migrates producers to the repo path.

## Lifecycle

```text
Producer append (status=queued)
  → auto_intake marks processing
  → bd create / claim OR bead_dispatch route
  → status=processed | failed | skipped
  → workflow_go / close-issue on bd ready
  → closure appends follow_up (kind=follow_up) back to queue
```

## Entry kinds

| `kind` | Meaning | `auto_intake` action |
|--------|---------|----------------------|
| `goal` | High-level goal text in `goal` field | Decompose → multiple `bd create` |
| `bead_dispatch` | Bead already exists (`bead_id`) | Classify tier, optional claim, hand to router |
| `follow_up` | Discovered work from closure magnet | `bd create` (+ optional claim) |

## Drain queue

```bash
# Scheduled / one-shot cycle (poll + drain + audit log):
powershell -File scripts/run_intake_cycle.ps1   # Windows
bash scripts/run_intake_cycle.sh                # WSL/Linux

python scripts/poll_inbox.py              # inbox sqlite → intake_queue.jsonl
python scripts/auto_intake.py              # drain → beads
python scripts/auto_intake.py --dry-run
python scripts/auto_intake.py --limit 5
```

Ops runbook: [docs/ops/HARNESS_AUTOMATION_RUNBOOK.md](ops/HARNESS_AUTOMATION_RUNBOOK.md)

`goal` entries use **simple bullet decomposition** (no LLM) in P0; full GoalDecomposer is a later enhancement.

## Sources

| `source` | Producer |
|----------|----------|
| `bead_hook` | `.beads/hooks/bead-intake.sh` after `bd create` |
| `closure` | Session compact / closure magnet |
| `inbox` | Chromatic Inbox Harness adapter (`scripts/poll_inbox.py`) |
| `manual` | Human or agent `python -m intake.queue append` |
| `goal` | `intake_queue.jsonl` direct append |
| `workflow` | `workflow_go` / task graph completion |

## Example records

**Goal (needs decomposition):**

```json
{"id":"goal-20260529-001","source":"manual","kind":"goal","status":"queued","title":"Wire intake loop E2E","goal":"Implement validate_intake_loop.py and document producers","priority":"P1","type":"task","tier":3,"queued_at":"2026-05-29T12:00:00Z"}
```

**Bead dispatch (hook after bd create):**

```json
{"id":"chromatic-harness-v2-nev","source":"bead_hook","kind":"bead_dispatch","status":"queued","title":"Route bead-intake hook to repo intake queue","bead_id":"chromatic-harness-v2-nev","priority":"P1","type":"task","tier":1,"queued_at":"2026-05-29T12:05:00Z"}
```

**Follow-up from closure:**

```json
{"id":"fu-chr-mission-abc","source":"closure","kind":"follow_up","status":"queued","title":"Add OTel span to closure magnet","goal":"Emit gen_ai span when mission closes","priority":"P2","type":"task","tier":2,"context":{"parent_mission":"CHR-ABC"},"queued_at":"2026-05-29T18:00:00Z"}
```

## Python API

```python
from intake.queue import default_queue_path, append_entry, list_queued, validate_entry

append_entry({"id": "...", "source": "manual", "kind": "goal", ...})
for entry in list_queued():
    ...
```

## Rules

1. **Append only** — never rewrite the file in place; status updates append a new line or use sidecar state in `4ie` (processor tracks last-seen ids).
2. **Dedupe by `id`** — producers must not re-append the same `id` while `status=queued`.
3. **No secrets** in `context` — queue may be committed to git.
4. **Close loop before expansion** — inbox adapter and MCP server wait until P0 E2E bead `1o2` passes.

## Related

- [V2_CONSOLIDATION_BEADS.md](research/V2_CONSOLIDATION_BEADS.md)
- [CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md](research/CHROMATIC_HARNESS_V2_GAPS_AND_ECOSYSTEM_LANDSCAPE.md) — Gap 5 Auto-Intake
