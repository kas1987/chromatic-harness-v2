# Successor Agent Prompt

**Transfer ID:** 95b21f5e-8c24-442b-ba68-d4aac4fe0342
**Budget decision:** halt_human

## Objective

Continue harness mission from handoff

## Summary

Session closeout (claude_code). Budget decision: halt_human.

## Next action

bd ready

## Risks

- monthly cap reached ($11492.76 >= $400.00)

## Handoff

- Markdown: `12_HANDOFFS/sessions/SESSION.md`
- Packet: `.agents/handoffs/transfer_packet.json`

## Boot (run first)

- `python scripts/new_session_bootstrap.py --root .`
- `bd ready`

Do not load full transcripts or bulk JSONL logs.