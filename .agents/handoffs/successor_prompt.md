# Successor Agent Prompt

**Transfer ID:** 2f560ec6-79a7-44be-9cec-edfbdd3a0bcb
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