import { BUDGET, assertBudgetAllows, compressToHandoff } from './_budget.js'

export const meta = {
  name: 'close-issue',
  description: 'Lite close: implement one bead → pytest → push. Budget-gated.',
  phases: [
    { title: 'Implement', detail: 'Single beads issue' },
    { title: 'Verify', detail: 'pytest subset or full' },
    { title: 'Push', detail: 'git push' },
  ],
}

// Usage: /close-issue <bead-id>
// NO /post-mortem council — run /post-mortem manually when epic ends

const issueId = args
if (!issueId) throw new Error('Usage: /close-issue <bead-id>')

phase('Implement')
assertBudgetAllows({
  phase: 'implement',
  estimatedTokens: 30000,
  estimatedToolCalls: 8,
  estimatedFilesRead: 10,
  touchesTranscripts: false,
})
const impl = await agent(
  `Run /implement for beads issue ${issueId} only.
Claim, implement, commit. Output: commit hash + files changed (list, not full diff).`,
  { label: `implement:${issueId}`, phase: 'Implement' }
)
const implPacket = compressToHandoff('implement', { summary: impl })

phase('Verify')
assertBudgetAllows({
  phase: 'verify',
  estimatedTokens: 18000,
  estimatedToolCalls: 4,
  estimatedFilesRead: 6,
  touchesTranscripts: false,
})
const tests = await agent(
  `Run: python -m pytest tests/ -q --tb=line
Issue context: ${issueId}
Prior handoff: ${JSON.stringify(implPacket)}`,
  { label: 'verify', phase: 'Verify' }
)

phase('Ship')
const shipPlan = await bash(
  `python scripts/workflow_git.py plan --confidence 90 --verifier approve --tests-passed --bead-id ${issueId}`
)
let ship
try {
  ship = JSON.parse(shipPlan.trim())
} catch {
  ship = { pipeline: { commit: false } }
}

if (ship.pipeline && ship.pipeline.commit) {
  await bash(
    `python scripts/workflow_git.py ship --execute --confidence 90 --verifier approve --tests-passed --bead-id ${issueId} --message "feat: close ${issueId}"`
  )
} else {
  assertBudgetAllows({
    phase: 'ship-blocked',
    estimatedTokens: 8000,
    estimatedToolCalls: 2,
    estimatedFilesRead: 2,
    touchesTranscripts: false,
  })
  await agent(
    `Confidence gate blocked auto-ship. Summary packet: ${JSON.stringify(compressToHandoff('ship', { summary: shipPlan }))}
Human must review and push manually if appropriate.`,
    { label: 'ship-blocked', phase: 'Ship' }
  )
}

await bash(`bd close ${issueId}`)

return { issueId, status: 'closed-lite', verify: compressToHandoff('verify', { summary: tests }), budget: BUDGET.class }
