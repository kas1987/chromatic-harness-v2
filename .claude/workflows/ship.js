import { BUDGET, assertBudgetAllows, compressToHandoff } from './_budget.js'

export const meta = {
  name: 'ship',
  description: 'Lite ship: discovery + plan → beads handoff. NO crank. Budget-gated.',
  phases: [
    { title: 'Discover', detail: 'Research summary only — no full /discovery epic' },
    { title: 'Plan', detail: 'Beads issues + handoff pointer' },
    { title: 'Handoff', detail: 'Write next_command for human or /close-issue' },
  ],
}

// Usage: /ship <feature description>
// DO NOT chain /crank here — see ship.HEAVY.js.bak and docs/AGENT_ANTIPATTERNS.md

const feature = args || 'feature (no description provided)'

phase('Discover')
assertBudgetAllows({
  phase: 'discover',
  estimatedTokens: 20000,
  estimatedToolCalls: 6,
  estimatedFilesRead: 8,
  touchesTranscripts: false,
})
const discovery = await agent(
  `Research and summarize scope for: "${feature}".
Use bd and repo docs only. Output: goal, risks, 3-5 tasks (titles only).
Do NOT run /crank, /swarm, or /council. Max 800 words.`,
  { label: 'discover-lite', phase: 'Discover' }
)
const discoveryPacket = compressToHandoff('discover', { summary: discovery })

phase('Plan')
assertBudgetAllows({
  phase: 'plan',
  estimatedTokens: 22000,
  estimatedToolCalls: 5,
  estimatedFilesRead: 6,
  touchesTranscripts: false,
})
const plan = await agent(
  `Create beads issues for this scope (bd create). Output ONLY:
- epic or parent bead id (if any)
- list of bead ids + titles
- suggested branch name
Do NOT implement code.

Scope handoff packet (compressed):
${JSON.stringify(discoveryPacket)}`,
  { label: 'plan-lite', phase: 'Plan' }
)
const planPacket = compressToHandoff('plan', { summary: plan })

phase('Handoff')
assertBudgetAllows({
  phase: 'handoff',
  estimatedTokens: 12000,
  estimatedToolCalls: 3,
  estimatedFilesRead: 4,
  touchesTranscripts: false,
})
await agent(
  `Update .agents/handoffs/latest.json pointer with branch, beads_ready from handoff packet:
${JSON.stringify(planPacket)}

Tell the user to run: bd ready
Then: /close-issue <bead-id> for ONE issue at a time.`,
  { label: 'handoff', phase: 'Handoff' }
)

return { feature, status: 'planned', budget: BUDGET.class, next: 'bd ready && /close-issue <id>' }
