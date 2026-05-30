export const meta = {
  name: 'hotfix',
  description: 'Lite hotfix: root cause → minimal patch → pytest → push. (~40-100k tok)',
  phases: [
    { title: 'Diagnose', detail: 'Targeted bug-hunt' },
    { title: 'Patch', detail: 'Minimal fix' },
    { title: 'Verify', detail: 'pytest + push' },
  ],
}

import { assertBudgetAllows } from './_budget.js'

const bug = args || 'bug (no description provided)'

phase('Diagnose')
assertBudgetAllows({
  phase: 'diagnose',
  estimatedTokens: 18000,
  estimatedToolCalls: 4,
  estimatedFilesRead: 5,
  touchesTranscripts: false,
})
const hunt = await agent(
  `Diagnose: "${bug}". Read only files needed. Output: root cause, fix plan, files to touch.
Do NOT run /security-suite or /council. Max 500 words.`,
  { label: 'diagnose', phase: 'Diagnose' }
)

phase('Patch')
assertBudgetAllows({
  phase: 'patch',
  estimatedTokens: 18000,
  estimatedToolCalls: 5,
  estimatedFilesRead: 6,
  touchesTranscripts: false,
})
const patch = await agent(
  `Minimal fix only. No refactor.

Plan:
${hunt.slice(0, 2500)}`,
  { label: 'patch', phase: 'Patch' }
)

phase('Verify')
assertBudgetAllows({
  phase: 'verify',
  estimatedTokens: 14000,
  estimatedToolCalls: 3,
  estimatedFilesRead: 3,
  touchesTranscripts: false,
})
await agent(
  `python -m pytest tests/ -q --tb=line
Then git pull --rebase && git push with concise commit message.

Patch summary: ${patch.slice(0, 1000)}`,
  { label: 'verify-push', phase: 'Verify' }
)

return { bug, status: 'hotfixed-lite' }
