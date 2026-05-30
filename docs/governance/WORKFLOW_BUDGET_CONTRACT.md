# Workflow Budget Contract

## Purpose

This contract defines the maximum allowed token, tool, file, and output budgets for Claude workflows.

## Budget Classes

| Class | Max Context Read | Max Tool Calls | Max Files Read | Max Output Per Phase | Transcript Access |
|---|---:|---:|---:|---:|---|
| Lite | 25k | 6 | 4 | 1,000 tokens | Forbidden |
| Normal | 75k | 12 | 10 | 1,500 tokens | Forbidden by default |
| Audit Lite | 40k | 8 | 6 | 1,500 tokens | Summary index only |
| Deep Audit | Approval required | Approval required | Approval required | 2,000 tokens | Explicit approval only |
| Swarm Deep | Approval required | Approval required | Approval required | 2,000 tokens | Forbidden unless approved |

## Required Budget Header

Every workflow must define:

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

## Cost Gate Rule

Before every `agent()` call, run a cost gate check.

```js
assertBudgetAllows({
  phase: "plan",
  estimatedTokens: 18000,
  estimatedToolCalls: 2,
  estimatedFilesRead: 3
});
```

If the check fails, the workflow must compress context or halt.
