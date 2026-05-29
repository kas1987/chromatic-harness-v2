export const meta = {
  name: 'go',
  description: 'Lite GO: workflow_go → one bounded agent → verify. NO crank/swarm. (~30-80k tok)',
  phases: [
    { title: 'Score', detail: 'python scripts/workflow_go.py GO' },
    { title: 'Execute', detail: 'One agent on bead if decision=execute' },
    { title: 'Verify', detail: 'workflow_go GO VERIFY' },
  ],
}

// Usage: /go [GO | GO AUDIT | GO VERIFY | GO BUILD]
// DO NOT run /crank, /swarm, or /council — docs/AGENT_ANTIPATTERNS.md

const modeArg = (args || 'GO').trim()
const modeLabel = modeArg.toUpperCase().startsWith('GO') ? modeArg : `GO ${modeArg}`

phase('Score')
const scoreRaw = await bash(`python scripts/workflow_go.py ${JSON.stringify(modeLabel)}`)
let score
try {
  score = JSON.parse(scoreRaw.trim().split('\n').pop())
} catch {
  score = { decision: 'halt', raw: scoreRaw.slice(0, 2000) }
}

if (
  score.decision === 'halt' ||
  score.decision === 'plan_only' ||
  score.decision === 'self_heal' ||
  score.error
) {
  return {
    mode: modeLabel,
    status: score.decision || 'halt',
    score,
    next: score.next || 'bd ready',
  }
}

if (score.decision !== 'execute') {
  return { mode: modeLabel, status: score.decision, score }
}

phase('Execute')
const beadId = score.bead_id || 'unknown'
const work = await agent(
  `Implement bead ${beadId}: ${score.bead_title || ''}.
Rules: scoped changes only; do NOT run /crank, /swarm, or /council.
Run pytest on touched areas. Max 600 words summary.`,
  { label: 'go-lite-execute', phase: 'Execute' }
)

phase('Verify')
await bash('python scripts/workflow_go.py "GO VERIFY"')
const verifyNote = work.slice(0, 1500)
const shipRaw = await bash(
  'python scripts/workflow_git.py ship --from-log --verifier approve --run-tests --bead-id ' + beadId
)
let ship
try {
  ship = JSON.parse(shipRaw.trim())
} catch {
  ship = { pipeline: {} }
}

if (ship.pipeline && ship.pipeline.merge) {
  await bash(
    `python scripts/workflow_git.py ship --execute --from-log --verifier approve --tests-passed --bead-id ${beadId}`
  )
}

return {
  mode: modeLabel,
  status: ship.pipeline?.merge ? 'shipped' : 'verified_pending_human',
  bead_id: beadId,
  summary: verifyNote,
  git_pipeline: ship.pipeline,
  next: ship.pipeline?.merge ? `merged ${beadId}` : `bd close ${beadId} when satisfied`,
}
