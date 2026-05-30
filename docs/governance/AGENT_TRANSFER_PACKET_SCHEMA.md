# Agent Transfer Packet (ATP) Schema

## Purpose

Machine-readable successor bootstrap at session end. Extends [HANDOFF_PACKET_SCHEMA.md](HANDOFF_PACKET_SCHEMA.md) with budget and routing fields.

## Runtime path

- **Live:** `.agents/handoffs/transfer_packet.json` (may be gitignored; regenerated each closeout)
- **Example:** [docs/handoffs/transfer_packet.example.json](../handoffs/transfer_packet.example.json)

## Required top-level fields

| Field | Type | Description |
|-------|------|-------------|
| `transfer_id` | string (uuid) | Unique closeout id |
| `updated_at` | ISO-8601 UTC | Packet generation time |
| `source_runtime` | enum | `cursor`, `claude_code`, `vscode`, `cli`, `codex` |
| `objective` | string | Current mission objective |
| `decision` | string | Handoff decision string |
| `summary` | string | Max ~500 words |
| `evidence_refs` | string[] | Paths/commits only |
| `files_touched` | string[] | Repo-relative paths |
| `risks` | string[] | |
| `blockers` | string[] | |
| `next_action` | string | |
| `confidence` | number | 0–100 |
| `budget_used` | object | Per HANDOFF_PACKET_SCHEMA |
| `successor` | object | See below |
| `budget` | object | See below |
| `beads_ready` | string[] | Issue ids |
| `boot_commands` | string[] | Repo scripts for next session |
| `forbidden` | string[] | e.g. `full_transcript`, `bulk_jsonl_scan` |
| `handoff_path` | string | Markdown handoff relative path |
| `latest_pointer` | string | `.agents/handoffs/latest.json` |

## `successor` object

```json
{
  "runtime": "cursor",
  "model_hint": "",
  "spawn_mode": "auto",
  "prompt_path": ".agents/handoffs/successor_prompt.md"
}
```

`spawn_mode`: `auto` | `manual` (set `manual` when budget decision is not `spawn`).

## `budget` object

```json
{
  "session_est_tokens": 0,
  "session_cap_tokens": 200000,
  "daily_spent_usd": 0.0,
  "daily_cap_usd": 25.0,
  "monthly_spent_usd": 0.0,
  "monthly_cap_usd": 400.0,
  "decision": "spawn",
  "reasons": []
}
```

`decision` enum: `spawn` | `handoff_only` | `halt_human`

## Rules

- No full transcripts or JSONL blobs in the packet.
- `successor_prompt.md` is the only prose file passed to auto-spawn adapters.
- Later agents load ATP + `latest.json`, not prior chat.
