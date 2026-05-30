# Successor Agent Prompt

**Transfer ID:** 5f28b40d-5115-49c1-9e93-7f2cd6f3ac1c
**Budget decision:** spawn

## Objective

Continue harness mission from handoff

## Summary

Session closeout (cursor). Budget decision: spawn.

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