/** Shared token budget helpers for lite workflows — see docs/governance/WORKFLOW_BUDGET_CONTRACT.md */

export const BUDGET = {
  class: 'normal',
  maxToolCalls: 12,
  maxFilesRead: 10,
  maxContextTokens: 75000,
  maxOutputTokensPerPhase: 1500,
  transcriptAccess: 'forbidden',
  requiresDeepApproval: false,
}

export function assertBudgetAllows(estimate) {
  if (estimate.estimatedTokens > BUDGET.maxContextTokens) {
    throw new Error(`Budget exceeded in ${estimate.phase}: estimated tokens too high`)
  }
  if (estimate.estimatedToolCalls > BUDGET.maxToolCalls) {
    throw new Error(`Budget exceeded in ${estimate.phase}: too many tool calls`)
  }
  if (estimate.estimatedFilesRead > BUDGET.maxFilesRead) {
    throw new Error(`Budget exceeded in ${estimate.phase}: too many files read`)
  }
  if (BUDGET.transcriptAccess === 'forbidden' && estimate.touchesTranscripts) {
    throw new Error(`Transcript access forbidden in ${estimate.phase}`)
  }
}

export function compressToHandoff(phaseName, output) {
  const text = typeof output === 'string' ? output : String(output?.summary || output || '')
  return {
    phase: phaseName,
    objective: output?.objective || '',
    decision: output?.decision || '',
    summary: text.slice(0, 3000),
    evidence_refs: output?.evidence_refs || [],
    files_touched: output?.files_touched || [],
    risks: output?.risks || [],
    blockers: output?.blockers || [],
    next_action: output?.next_action || '',
    confidence: output?.confidence || 0,
    budget_used: output?.budget_used || { tool_calls: 0, files_read: 0, approx_tokens: 0 },
  }
}
