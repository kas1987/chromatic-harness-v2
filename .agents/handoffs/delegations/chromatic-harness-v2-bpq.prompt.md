# Claude Delegation Packet

Timestamp: 2026-05-30T06:24:52.845547+00:00
Bead: chromatic-harness-v2-bpq
T-level: T2
Complexity: C3
Privacy: P1

## Objective
Production-readiness analysis and implementation plan for EPIC PDR folder completion sweep

## Governance
- Pre-swarm gate passed: True
- Confidence decision: execute
- Mutation allowed: True

## Routing Recommendation
- gemini (gemini-2.5-pro) :: routing table: context_laptop/balance/C3
- openrouter (moonshotai/kimi-k2-6) :: routing table: context_laptop/balance/C3
- claude_api (sonnet) :: routing table: context_laptop/balance/C3

## Required Guardrails
- Use bd for tracking; no TodoWrite authority.
- Stay within assigned file scope.
- If confidence drops to plan_only/halt, stop mutation and return plan.

## Packet Reference
- .agents/handoffs/claude_delegate_packet.json
