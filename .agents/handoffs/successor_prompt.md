# Successor Agent Prompt

**Transfer ID:** c7c8dced-7893-4c53-bbca-79f70b8bb800
**Budget decision:** spawn

## Objective

Continue harness mission from handoff

## Summary

Session closeout (claude_code). Budget decision: spawn.

## Next action

bd ready

## Risks

- budget headroom OK for successor spawn

## Handoff

- Markdown: `12_HANDOFFS/sessions/SESSION.md`
- Packet: `.agents/handoffs/transfer_packet.json`

## Boot (run first)

- `python scripts/new_session_bootstrap.py --root .`
- `bd ready`

Do not load full transcripts or bulk JSONL logs.