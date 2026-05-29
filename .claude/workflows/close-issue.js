export const meta = {
  name: 'close-issue',
  description: 'Lite close: implement one bead → pytest → push. (~30-80k tok)',
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
const impl = await agent(
  `Run /implement for beads issue ${issueId} only.
Claim, implement, commit. Output: commit hash + files changed (list, not full diff).`,
  { label: `implement:${issueId}`, phase: 'Implement' }
)

phase('Verify')
const tests = await agent(
  `Run: python -m pytest tests/ -q --tb=line
Issue context: ${issueId}
Prior summary: ${impl.slice(0, 1500)}`,
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
  await agent(
    `Confidence gate blocked auto-ship. Summary: ${shipPlan.slice(0, 1200)}
Human must review and push manually if appropriate.`,
    { label: 'ship-blocked', phase: 'Ship' }
  )
}

await bash(`bd close ${issueId}`)

return { issueId, status: 'closed-lite' }
