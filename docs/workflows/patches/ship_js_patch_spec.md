# Patch Spec: `ship.js` Token Governance Update

## Objective

Modify `ship.js` so it no longer passes full prior phase output into later workflow phases.

## Required Changes

### 1. Add budget constants

```js
const BUDGET = {
  class: "normal",
  maxToolCalls: 12,
  maxFilesRead: 10,
  maxContextTokens: 75000,
  maxOutputTokensPerPhase: 1500,
  transcriptAccess: "forbidden",
  requiresDeepApproval: false
};
```

### 2. Add cost gate function

```js
function assertBudgetAllows(estimate) {
  if (estimate.estimatedTokens > BUDGET.maxContextTokens) {
    throw new Error(`Budget exceeded in ${estimate.phase}: estimated tokens too high`);
  }
  if (estimate.estimatedToolCalls > BUDGET.maxToolCalls) {
    throw new Error(`Budget exceeded in ${estimate.phase}: too many tool calls`);
  }
  if (estimate.estimatedFilesRead > BUDGET.maxFilesRead) {
    throw new Error(`Budget exceeded in ${estimate.phase}: too many files read`);
  }
  if (BUDGET.transcriptAccess === "forbidden" && estimate.touchesTranscripts) {
    throw new Error(`Transcript access forbidden in ${estimate.phase}`);
  }
}
```

### 3. Add handoff compression

```js
function compressToHandoff(phaseName, output) {
  return {
    objective: output.objective || "",
    decision: output.decision || "",
    summary: String(output.summary || output).slice(0, 3000),
    evidence_refs: output.evidence_refs || [],
    files_touched: output.files_touched || [],
    risks: output.risks || [],
    blockers: output.blockers || [],
    next_action: output.next_action || "",
    confidence: output.confidence || 0,
    budget_used: output.budget_used || {
      tool_calls: 0,
      files_read: 0,
      approx_tokens: 0
    }
  };
}
```

### 4. Replace full-output chaining

Forbidden:

```js
const crank = await agent(`/crank ${discovery}\n${plan}`);
```

Required:

```js
const planPacket = compressToHandoff("plan", plan);
assertBudgetAllows({
  phase: "crank",
  estimatedTokens: 25000,
  estimatedToolCalls: 4,
  estimatedFilesRead: 5,
  touchesTranscripts: false
});
const crank = await agent("/crank", { context: planPacket });
```

## Acceptance Tests

- No `agent()` call receives raw concatenated prior outputs.
- Every phase has an `assertBudgetAllows()` check.
- Transcript access is blocked unless deep mode is approved.
- Phase outputs are compressed to handoff packets.
