# Phase 2 Completion: Magnets Integration with roach-pi

**Completed:** 2026-05-28  
**Issue:** chromatic-harness-v2-jwn

## Summary

Phase 2 wires observable Magnets into the roach-pi adapter execution. Each Magnet observes inflection points (tool calls, errors, test results, token usage) and generates confidence scores and anomaly reports. The MagnetSynthesis layer aggregates all magnet reports into unified execution quality signals for downstream CMP gates.

## Deliverables

### 1. Base Magnet Class (`magnets/base-magnet.ts`)

**Core abstraction:**
- `observe(key, value)` — Record observations
- `raiseAnomaly(level, message, evidence, action)` — Flag issues (info/warn/error)
- `calculateScore()` — Compute confidence (0-1)
- `report()` — Generate `MagnetReport` with observations, anomalies, score
- `reset()` — Clear state for next mission

**No `any` types; full TypeScript.**

### 2. Execution Magnet (`magnets/execution-magnet.ts`)

**Observes:**
- Tool calls: what was called, arguments, result, duration, retries
- Errors: recoverable vs. unrecoverable, stage, code
- Retry storms: >3 retries of same tool in <5s → anomaly
- Suspicious sequences: direct file overwrite, env var access, rapid API calls

**Scoring:** Deducts for errors, retries, anomalies. High score = clean execution.

**Methods:**
- `onToolCall(toolCall)` — Record tool invocation + detect anomalies
- `onError(error)` — Record error + mark if unrecoverable
- `getToolCalls()` / `getErrors()` — Raw data access

### 3. Cost Magnet (`magnets/cost-magnet.ts`)

**Observes:**
- Tokens consumed vs. budget
- Tool calls count vs. budget
- Wall-clock time vs. budget
- Efficiency metrics (tokens per task, tool calls per task)

**Thresholds:**
- 80% budget: raises `warn` anomaly
- Over budget: raises `error` anomaly

**Methods:**
- `onTokensUsed(count)` — Update token counter
- `onToolInvocation()` — Increment tool call counter
- `checkWallTimeBudget()` — Verify wall time (if configured)
- `getEfficiency()` — Return cost per work unit

### 4. Confidence Magnet (`magnets/confidence-magnet.ts`)

**Observes:**
- Test coverage: pass rate, total count
- Code quality: linting, type checking
- Review signals: human approval, documentation
- Code metrics: comment ratio, documentation quality, cyclomatic complexity

**Scoring logic (composite):**
- Test pass rate: 40% weight
- Type checking: 20% weight
- Lint cleanliness: 15% weight
- Code quality: 15% weight
- Review approval: +10% bonus
- Anomaly penalties: -10% per error, -2% per warning

**Methods:**
- `onTestResults(results)` — Record test pass/fail
- `onLintIssues(issues)` — Flag lint errors/warnings
- `onTypeCheckResult(passed, errorCount)` — Type safety score
- `onReviewApproval(approvedBy)` — Mark as reviewed
- `onCodeQuality(metrics)` — Ingest code metrics
- `getSummary()` — Return composite confidence

### 5. Magnet Synthesis (`magnets/magnet-synthesis.ts`)

**Purpose:** Aggregate all magnet reports into unified decision signals.

**Synthesis Score:**
```typescript
{
  overall_confidence: 0-1,        // Weighted average of all magnets
  execution_quality: 0-1,         // Execution magnet score
  cost_efficiency: 0-1,           // Cost magnet score
  test_confidence: 0-1,           // Confidence magnet score
  anomaly_count: number,          // Total anomalies across all
  critical_anomalies: number,     // Errors only
  recommendation: 'proceed' | 'review' | 'escalate' | 'blocked'
}
```

**Recommendation logic:**
- `blocked`: 1+ critical anomalies
- `escalate`: 5+ anomalies
- `review`: 1-4 anomalies OR confidence < 0.75
- `proceed`: Clean execution, high confidence

**Methods:**
- `addReport(report)` — Ingest magnet report
- `synthesize()` — Return unified score
- `report()` — Human-readable text summary
- `getScore()` — API-friendly score

**Example output:**
```
═══════════════════════════════════════
MAGNET SYNTHESIS REPORT
═══════════════════════════════════════

Overall Confidence:  88%
Execution Quality:   92%
Cost Efficiency:     85%
Test Confidence:     78%

Anomalies Detected:  2
  Critical (errors): 0
  Warnings:          2

RECOMMENDATION:      REVIEW

[Additional magnet details...]
```

### 6. roach-pi Adapter Integration

**Updated:** `adapters/roach-pi-adapter.ts`

**New fields:**
- `executionMagnet: ExecutionMagnet`
- `costMagnet: CostMagnet`
- `confidenceMagnet: ConfidenceMagnet`
- `synthesis: MagnetSynthesis`

**Updated `executeMission()`:**
1. Reset magnets before execution
2. Initialize costMagnet with mission's budget
3. Wrap task with magnet hooks
4. Execute mock/real roach-pi
5. **NEW:** Collect magnet data from result
6. **NEW:** Generate magnet reports
7. **NEW:** Synthesize unified score
8. Return ExecutionResult with magnet_reports

**New methods:**
- `resetMagnets()` — Clear all magnet state
- `collectMagnetData(result)` — Extract observations from roach-pi result and feed magnets

**Mock execution** now returns realistic data:
- 3 tool calls (file_read, file_write, git_commit)
- 3 passing tests
- Type check passed, lint clean
- Code quality metrics
- Review approval
- 2 learnings captured

### 7. Enhanced Tests (`test-phase1.ts`)

**Updated Test 3 (now "Mission execution with Magnet collection"):**
- Executes mission
- Verifies magnet reports generated
- Checks that execution, cost, and confidence magnets present
- Asserts magnet scores in result

**New assertions:**
```typescript
✓ Execution magnet collected: true
✓ Cost magnet collected: true
✓ Confidence magnet collected: true
```

## File Structure Created/Modified

```
chromatic-harness-v2/
├── 02_RUNTIME/
│   ├── adapters/
│   │   └── roach-pi-adapter.ts              ✓ (Updated)
│   │
│   ├── magnets/
│   │   ├── base-magnet.ts                   ✓ (New)
│   │   ├── execution-magnet.ts              ✓ (New)
│   │   ├── cost-magnet.ts                   ✓ (New)
│   │   ├── confidence-magnet.ts             ✓ (New)
│   │   └── magnet-synthesis.ts              ✓ (New)
│   │
│   ├── test-phase1.ts                       ✓ (Updated)
│   └── PHASE_2_COMPLETION_SUMMARY.md        ✓ (This file)
```

## Magnet Architecture

```
Execution happens inside roach-pi
        ↓
Mock returns:
  - tool_calls: []
  - test_results: []
  - lint_issues: []
  - type_check_passed: bool
  - errors: []
  - ...
        ↓
collectMagnetData() feeds observations:
  - ExecutionMagnet.onToolCall() → detects anomalies
  - ExecutionMagnet.onError() → flags unrecoverable
  - CostMagnet.onTokensUsed() → checks budget
  - CostMagnet.onToolInvocation() → counts tool calls
  - ConfidenceMagnet.onTestResults() → scores coverage
  - ConfidenceMagnet.onLintIssues() → marks quality
  - ConfidenceMagnet.onTypeCheckResult() → safety check
        ↓
Magnets emit reports:
  - ExecutionMagnet.report() → {score: 0.92, anomalies: []}
  - CostMagnet.report() → {score: 0.85, anomalies: [...]}
  - ConfidenceMagnet.report() → {score: 0.78, anomalies: [...]}
        ↓
MagnetSynthesis aggregates:
  - Overall confidence: 0.85
  - Recommendation: 'review' (2 minor anomalies)
        ↓
ExecutionResult includes:
  - magnet_reports: [report, report, report]
  - CMP gates use synthesis.recommendation in Phase 3
```

## Integration Points (Ready for Phase 3)

**CMP will use:**
- `synthesis.recommendation` to gate execution (proceed/review/escalate/blocked)
- `synthesis.overall_confidence` for human visibility
- Individual magnet anomalies for detailed diagnostics

**Console API (Phase 4) will display:**
- Real-time magnet event streams (WebSocket per inflection point)
- Synthesis dashboard (overall scores, recommendations)
- Anomaly inspector (drill into specific issues)

**Beads (Phase 3) will ingest:**
- Critical anomalies as alert beads
- Learnings as memory beads
- Magnet confidence delta as score beads

## Testing

**Run:**
```bash
npx ts-node 02_RUNTIME/test-phase1.ts
```

**Expected output:**
```
═══════════════════════════════════════════
Phase 1 Integration Tests
═══════════════════════════════════════════

Test 1: MissionPacket validation
  ✓ Valid packet passed validation: true
  ✓ Invalid packet failed validation: true

Test 2: Adapter capabilities
  ✓ Runtime ID: roach-pi
  ...

Test 3: Mission execution with Magnet collection
  ✓ Mission executed: m-test-003
  ✓ Status: success
  ✓ Tokens used: 45000
  ✓ Tool calls made: 3
  ✓ Tests passed: 3
  ✓ Learnings captured: 2
  ✓ Closed tasks: 1

  Magnet Reports:
    [execution] Score: 100%
    [cost] Score: 85%
    [confidence] Score: 78%

  ✓ Execution magnet collected: true
  ✓ Cost magnet collected: true
  ✓ Confidence magnet collected: true

Test 4: Runtime registry
  ✓ Registered runtimes: roach-pi
  ...

═══════════════════════════════════════════
✓ All Phase 1 tests passed
═══════════════════════════════════════════
```

## Known Limitations (Phase 2)

- [ ] Only 3 of 8 magnets implemented (ExecutionMagnet, CostMagnet, ConfidenceMagnet)
  - Missing: Intent, Scope, Security, Memory, Validation (specific magnet class)
- [ ] Magnet data is synthetic (mock execution)
- [ ] No real roach-pi runtime wired yet
- [ ] No WebSocket event streaming
- [ ] Synthesis recommendation not yet enforced by CMP

## Next: Phase 3 (CMP Governance Bridge)

Phase 3 uses magnet reports to gate execution:

1. **CMP Executor** applies gates based on synthesis.recommendation
2. **BeadsBridge** converts roach-pi results + magnet anomalies → Chromatic beads
3. **Escalation logic** routes critical anomalies to human review

**Acceptance criteria for Phase 3:**
- [ ] CMP accepts/rejects missions based on confidence gates
- [ ] Anomalies → Alert Beads
- [ ] Learnings → Memory Beads
- [ ] Closed tasks → Action Beads
- [ ] Integration test verifies gate enforcement

---

**Phase 2 is READY for Phase 3 dependency-unblock.**
