import { BUDGET, assertBudgetAllows, compressToHandoff } from './_budget.js'

export const meta = {
  name: 'go',
  description: 'Lite GO: workflow_go → self-heal cycle → bounded agent. NO crank/swarm.',
  phases: [
    { title: 'Score', detail: 'python scripts/workflow_go.py GO' },
    { title: 'Self-heal', detail: 'auto_intake + second GO when decision=self_heal' },
    { title: 'Execute', detail: 'One agent on bead if decision=execute' },
    { title: 'Verify', detail: 'workflow_go GO VERIFY' },
  ],
}

// Usage: /go [GO | GO AUDIT | GO VERIFY | GO BUILD]
// DO NOT run /crank, /swarm, or /council — docs/AGENT_ANTIPATTERNS.md

const modeArg = (args || 'GO').trim()
const modeLabel = modeArg.toUpperCase().startsWith('GO') ? modeArg : `GO ${modeArg}`

phase('Score')
assertBudgetAllows({
  phase: 'score',
  estimatedTokens: 8000,
  estimatedToolCalls: 2,
  estimatedFilesRead: 2,
  touchesTranscripts: false,
})
const scoreRaw = await bash(`python scripts/workflow_go.py ${JSON.stringify(modeLabel)}`)
let score
try {
  score = JSON.parse(scoreRaw.trim().split('\n').pop())
} catch {
  score = { decision: 'halt', raw: scoreRaw.slice(0, 2000) }
}

if (score.decision === 'halt' || score.error) {
  return {
    mode: modeLabel,
    status: score.decision || 'halt',
    score,
    next: score.next || 'bd ready',
  }
}

if (score.decision === 'self_heal') {
  phase('Self-heal')
  assertBudgetAllows({
    phase: 'self_heal',
    estimatedTokens: 15000,
    estimatedToolCalls: 4,
    estimatedFilesRead: 3,
    touchesTranscripts: false,
  })
  const cycleRaw = await bash('python scripts/workflow_self_heal_cycle.py --limit 10')
  let cycle
  try {
    cycle = JSON.parse(cycleRaw.trim().split('\n').pop())
  } catch {
    cycle = { status: 'parse_error', raw: cycleRaw.slice(0, 2000) }
  }
  score = cycle.final || score
  if (score.decision === 'plan_only' || score.decision === 'self_heal' || score.decision === 'halt') {
    return {
      mode: modeLabel,
      status: score.decision,
      score: compressToHandoff('go_after_cycle', score),
      cycle: compressToHandoff('self_heal_cycle', cycle),
      next: score.next || 'bd ready',
    }
  }
}

if (score.decision === 'plan_only') {
  return {
    mode: modeLabel,
    status: 'plan_only',
    score: compressToHandoff('score', score),
    next: score.next || 'GO DEEP or improve handoff',
  }
}

if (score.decision !== 'execute') {
  return { mode: modeLabel, status: score.decision, score: compressToHandoff('score', score) }
}

phase('Execute')
assertBudgetAllows({
  phase: 'execute',
  estimatedTokens: 25000,
  estimatedToolCalls: 8,
  estimatedFilesRead: 8,
  touchesTranscripts: false,
})
const beadId = score.bead_id || 'unknown'
const work = await agent(
  `Implement bead ${beadId}: ${score.bead_title || ''}.
Rules: scoped changes only; do NOT run /crank, /swarm, or /council.
Run pytest on touched areas. Max 600 words summary.`,
  { label: 'go-lite-execute', phase: 'Execute' }
)

phase('Verify')
await bash('python scripts/workflow_go.py "GO VERIFY"')
const verifyNote = compressToHandoff('execute', { summary: work })
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
  budget: BUDGET.class,
  next: ship.pipeline?.merge ? `merged ${beadId}` : `bd close ${beadId} when satisfied`,
}
