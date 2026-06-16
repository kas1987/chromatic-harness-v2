# Successor Agent Prompt

**Transfer ID:** f4e9bea5-d695-47af-b890-4bbca61343c9
**Budget decision:** halt_human

## Objective

Continue harness mission from handoff

## Summary

Session closeout (claude_code). Budget decision: halt_human.

## Next action

bd ready

## Risks

- monthly cap reached ($10840.14 >= $400.00)

## Handoff

- Markdown: `12_HANDOFFS/sessions/SESSION.md`
- Packet: `.agents/handoffs/transfer_packet.json`

## Boot (run first)

- `python scripts/new_session_bootstrap.py --root .`
- `bd ready`

Do not load full transcripts or bulk JSONL logs.