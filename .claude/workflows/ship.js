export const meta = {
  name: 'ship',
  description: 'Lite ship: discovery + plan → beads handoff. NO crank. (~50-150k tok)',
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
const discovery = await agent(
  `Research and summarize scope for: "${feature}".
Use bd and repo docs only. Output: goal, risks, 3-5 tasks (titles only).
Do NOT run /crank, /swarm, or /council. Max 800 words.`,
  { label: 'discover-lite', phase: 'Discover' }
)

phase('Plan')
const plan = await agent(
  `Create beads issues for this scope (bd create). Output ONLY:
- epic or parent bead id (if any)
- list of bead ids + titles
- suggested branch name
Do NOT implement code.

Scope summary:
${discovery.slice(0, 4000)}`,
  { label: 'plan-lite', phase: 'Plan' }
)

phase('Handoff')
await agent(
  `Update .agents/handoffs/latest.json pointer with branch, beads_ready from:
${plan.slice(0, 2000)}

Tell the user to run: bd ready
Then: /close-issue <bead-id> for ONE issue at a time.`,
  { label: 'handoff', phase: 'Handoff' }
)

return { feature, status: 'planned', next: 'bd ready && /close-issue <id>' }
