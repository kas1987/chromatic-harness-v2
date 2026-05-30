import { BUDGET, assertBudgetAllows, compressToHandoff } from './_budget.js'

export const meta = {
  name: 'qa',
  description: 'Lite QA: pytest + ruff only. Budget-gated. (~10-30k tok)',
  phases: [
    { title: 'Test', detail: 'pytest tests/' },
    { title: 'Lint', detail: 'ruff check + format' },
  ],
}

// Usage: /qa
// DO NOT run parallel /complexity /security /perf /vibe — see qa.HEAVY.js.bak

phase('Test')
assertBudgetAllows({
  phase: 'test',
  estimatedTokens: 15000,
  estimatedToolCalls: 4,
  estimatedFilesRead: 5,
  touchesTranscripts: false,
})
const tests = await agent(
  `Run: python -m pytest tests/ -q --tb=line
Report pass/fail count only. No subagents.`,
  { label: 'pytest', phase: 'Test' }
)

phase('Lint')
assertBudgetAllows({
  phase: 'lint',
  estimatedTokens: 12000,
  estimatedToolCalls: 3,
  estimatedFilesRead: 4,
  touchesTranscripts: false,
})
const lint = await agent(
  `Run: ruff check src/ tests/ 02_RUNTIME/ && ruff format --check src/ tests/
Report issues count only.`,
  { label: 'ruff', phase: 'Lint' }
)

return {
  tests: compressToHandoff('test', { summary: tests }),
  lint: compressToHandoff('lint', { summary: lint }),
  status: 'qa-lite-done',
  budget: BUDGET.class,
}
