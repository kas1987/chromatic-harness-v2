# Queue Mirror — GitHub Issue Sync (GH #51)

## What Phase 3 Shipped

GH #51 ("Mirror agent queue to GitHub issues") was implemented across three scripts
that together form the full bidirectional queue mirror:

| Script | Role |
|--------|------|
| `scripts/sync_queue_to_github.py` | Phase 3a — initial queue-to-GH issue creation/close from `01_STATE/AGENT_HANDOFF_QUEUE.md` |
| `scripts/queue_sync_mutations.py` | Phase 3b/3c — mutation mirroring (bead state → GH comment) + inbound close-sync |

### Phase 3a — `sync_queue_to_github.py`

Reads `01_STATE/AGENT_HANDOFF_QUEUE.md` and creates/closes GitHub issues labelled
`agent-queue` to mirror the queue state. Dry-run by default; pass `--execute` to write.

```bash
python scripts/sync_queue_to_github.py            # dry-run
python scripts/sync_queue_to_github.py --execute  # create/close GH issues
python scripts/sync_queue_to_github.py --execute --close-done  # also close done issues
```

### Phase 3b — Mutation Mirroring

When a bead transitions state (claimed → in_progress → closed/failed), `mirror_mutation()`
posts a comment on the bead's linked GH issue. All actions are logged to the audit trail
at `07_LOGS_AND_AUDIT/queue_sync/history.jsonl`.

```bash
python scripts/queue_sync_mutations.py --mirror <bead-id> claimed
python scripts/queue_sync_mutations.py --mirror <bead-id> closed --execute
```

### Phase 3c — Inbound Close-Sync

Closed agent-queue GH issues can mark their linked beads done:

```bash
python scripts/queue_sync_mutations.py --inbound-close-sync
python scripts/queue_sync_mutations.py --inbound-close-sync --execute
```

## Audit Trail

Every sync action is appended to `07_LOGS_AND_AUDIT/queue_sync/history.jsonl`.
Each record contains:

```json
{
  "timestamp": "2026-06-01T00:00:00Z",
  "action": "mutation_mirror | inbound_close | queue_sync",
  "bead_id": "gh-51",
  "issue_number": 51,
  "state": "closed",
  "status": "commented | bead_closed | dry_run | pending | error"
}
```

## Architecture

```
01_STATE/AGENT_HANDOFF_QUEUE.md
        │
        ▼ (sync_queue_to_github.py --execute)
GitHub Issues [label: agent-queue]
        │                 │
        │ bead transition │ issue closed externally
        ▼                 ▼
queue_sync_mutations.py   queue_sync_mutations.py
  mirror_mutation()         inbound_close_sync()
        │                         │
        ▼                         ▼
GH issue comment          bd close <bead-id>
        │
        ▼
07_LOGS_AND_AUDIT/queue_sync/history.jsonl
```

## What Is Still Pending

- **Automated trigger**: `mirror_mutation()` is currently called manually. Wiring it
  into `bd update` hooks for automatic invocation on every bead state change is not
  yet implemented.
- **GH issue body embeds `bead:<id>` reference**: `inbound_close_sync()` relies on the
  issue body containing a `bead:<id>` line. Issues created before Phase 3a do not carry
  this reference; they must be updated manually or re-created.

## Verification Steps

```bash
# 1. Confirm the queue parses cleanly (dry-run)
python scripts/sync_queue_to_github.py

# 2. Confirm mutation mirroring in dry-run mode
python scripts/queue_sync_mutations.py --mirror gh-51 claimed

# 3. Confirm inbound close-sync dry-run
python scripts/queue_sync_mutations.py --inbound-close-sync

# 4. Review audit trail
cat 07_LOGS_AND_AUDIT/queue_sync/history.jsonl | tail -20

# 5. Live sync (requires GH auth)
python scripts/sync_queue_to_github.py --execute
```

## Configuration

No mandatory configuration. Optional env vars:

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_PERSONAL_ACCESS_TOKEN` | (from settings.json) | GH auth for `gh` CLI |

The `gh` CLI must be authenticated (`gh auth status`) for `--execute` modes.
