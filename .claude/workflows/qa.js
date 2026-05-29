export const meta = {
  name: 'qa',
  description: 'Lite QA: pytest + ruff only. (~10-30k tok)',
  phases: [
    { title: 'Test', detail: 'pytest tests/' },
    { title: 'Lint', detail: 'ruff check + format' },
  ],
}

// Usage: /qa
// DO NOT run parallel /complexity /security /perf /vibe — see qa.HEAVY.js.bak

phase('Test')
const tests = await agent(
  `Run: python -m pytest tests/ -q --tb=line
Report pass/fail count only. No subagents.`,
  { label: 'pytest', phase: 'Test' }
)

phase('Lint')
const lint = await agent(
  `Run: ruff check src/ tests/ 02_RUNTIME/ && ruff format --check src/ tests/
Report issues count only.`,
  { label: 'ruff', phase: 'Lint' }
)

return { tests: tests.slice(0, 1500), lint: lint.slice(0, 1500), status: 'qa-lite-done' }
