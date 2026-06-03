# Successor Agent Prompt

**Transfer ID:** 72ecf35d-2a2a-4351-a64e-1dbc9e64385b
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