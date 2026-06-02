import { BUDGET, assertBudgetAllows, compressToHandoff } from './_budget.js'

export const meta = {
  name: 'audit',
  description:
    'Lite audit: bounded parallel read-only fan-out (Explore agents per slice) → structured findings. NO writes, NO crank.',
  phases: [
    { title: 'Fan-out', detail: 'one read-only Explore agent per audit slice (bounded)' },
    { title: 'Synthesize', detail: 'merge slice findings into one report' },
  ],
}

// Usage: /audit [comma-separated slices]  (default: the core 6)
// Read-only: agents must NOT write files. For the deep version, see the v3 roadmap audit method.
// DO NOT run /crank or /swarm (unbounded). This fan-out is fixed/bounded.

const DEFAULT_SLICES = [
  { key: 'runtime', scope: '02_RUNTIME/ — router, magnets, audit, workflows, api' },
  { key: 'automation', scope: 'scripts/, .claude/ hooks & workflows, git_hooks/' },
  { key: 'protocols', scope: '01_PROTOCOLS/, 00_SOURCE_OF_TRUTH/, schemas/' },
  { key: 'observability', scope: '07_LOGS_AND_AUDIT/, audit/two_log.py, cost/OTel' },
  { key: 'structure', scope: 'top-level layout, duplicate/legacy dirs (see CHROMATIC_TREES.md)' },
  { key: 'quality', scope: 'tests/, CI gates, readiness scoring' },
]

const requested = (args || '').trim()
const slices = requested
  ? requested.split(',').map((k) => DEFAULT_SLICES.find((s) => s.key === k.trim()) || { key: k.trim(), scope: k.trim() })
  : DEFAULT_SLICES

phase('Fan-out')
assertBudgetAllows({
  phase: 'fan-out',
  estimatedTokens: 60000,
  estimatedToolCalls: 12,
  estimatedFilesRead: 10,
  touchesTranscripts: false,
})
const findings = await parallel(
  slices.map((s) => () =>
    agent(
      `READ-ONLY audit of slice "${s.key}" — scope: ${s.scope}.
Read excerpts, not whole files. Do NOT write or edit anything.
Return a tight structured report: Inventory · Maturity (REAL/PARTIAL/STUB/MISSING + evidence) · Debt (cite paths) · v3 opportunities. Under 500 words.`,
      { label: `audit:${s.key}`, phase: 'Fan-out', agentType: 'Explore' }
    ).then((r) => compressToHandoff(`audit:${s.key}`, { summary: r }))
  )
)

phase('Synthesize')
assertBudgetAllows({
  phase: 'synthesize',
  estimatedTokens: 30000,
  estimatedToolCalls: 4,
  estimatedFilesRead: 4,
  touchesTranscripts: false,
})
const synthesis = await agent(
  `Synthesize these per-slice audit findings into ONE report: cross-cutting themes,
the top 5-8 highest-impact issues (with evidence), and a suggested epic list.
Map findings to existing v3 epics where they fit (bd list --label v3).
Do NOT write files unless asked. Max 900 words.

Slice findings (compressed):
${JSON.stringify(findings.filter(Boolean))}`,
  { label: 'audit-synthesize', phase: 'Synthesize' }
)

return {
  slices: slices.map((s) => s.key),
  status: 'audited',
  findings: compressToHandoff('synthesis', { summary: synthesis }),
  budget: BUDGET.class,
  next: '/plan <area> to turn a theme into an epic + beads, or update docs/research/*_ROADMAP.md',
}
