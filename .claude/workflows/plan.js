import { BUDGET, assertBudgetAllows, compressToHandoff } from './_budget.js'

export const meta = {
  name: 'plan',
  description:
    'Lite plan: decompose a goal/roadmap into ONE epic + child beads via templates + bd. NO implementation, NO crank.',
  phases: [
    { title: 'Decompose', detail: 'goal → epic + 3-8 child beads (titles + priorities)' },
    { title: 'Create', detail: 'bd create epic + children (--parent)' },
    { title: 'Map', detail: 'emit bead map + handoff pointer' },
  ],
}

// Usage: /plan <goal, or path to a roadmap doc>
// Templates: templates/EPIC_TEMPLATE.md + templates/BEAD_TEMPLATE.md
// Structure / where things live: CHROMATIC_TREES.md §6. DO NOT run /crank or /swarm.

const goal = args || 'goal (no description provided)'

phase('Decompose')
assertBudgetAllows({
  phase: 'decompose',
  estimatedTokens: 22000,
  estimatedToolCalls: 6,
  estimatedFilesRead: 8,
  touchesTranscripts: false,
})
const decomposition = await agent(
  `Decompose this goal into ONE epic and 3-8 child beads.
Goal: "${goal}".
Read templates/EPIC_TEMPLATE.md and templates/BEAD_TEMPLATE.md for structure, and
CHROMATIC_TREES.md for where artifacts live. Use bd and repo docs only.
Output ONLY:
- epic: { title, priority (P0-P4), label, one-line goal, acceptance }
- beads: [ { title, priority, one-line scope } ]  (each = one artifact + tests)
Do NOT create anything yet. Do NOT implement code. Max 700 words.`,
  { label: 'plan-decompose', phase: 'Decompose' }
)
const plan = compressToHandoff('decompose', { summary: decomposition })

phase('Create')
assertBudgetAllows({
  phase: 'create',
  estimatedTokens: 18000,
  estimatedToolCalls: 10,
  estimatedFilesRead: 3,
  touchesTranscripts: false,
})
const created = await agent(
  `Create the epic and beads from this plan with bd (per CHROMATIC_TREES.md §6 / BEADS_PLAYBOOK):
  1. bd create "<title>" --type epic -p <P> -l "<label>" -d "<goal>" --acceptance "<criteria>" --silent  (capture epic id)
  2. for each bead: bd create "<title>" --type task -p <P> --parent <epic-id> -l "<label>" -d "<scope>"
  3. bd dolt commit && bd dolt push
Output ONLY: epic id + list of bead ids + titles. Do NOT implement code.

Plan packet (compressed):
${JSON.stringify(plan)}`,
  { label: 'plan-create', phase: 'Create' }
)
const createdPacket = compressToHandoff('create', { summary: created })

phase('Map')
assertBudgetAllows({
  phase: 'map',
  estimatedTokens: 10000,
  estimatedToolCalls: 3,
  estimatedFilesRead: 2,
  touchesTranscripts: false,
})
await bash('bd ready')

return {
  goal,
  status: 'planned',
  epic_and_beads: createdPacket,
  budget: BUDGET.class,
  next: 'bd ready && /go (or /close-issue <bead-id>) for ONE bead at a time',
}
