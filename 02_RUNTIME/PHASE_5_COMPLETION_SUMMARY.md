# Phase 5 Completion: Sandbox Lab Agent Safety

**Completed:** 2026-05-28  
**Issue:** chromatic-harness-v2-g35

## Summary

Phase 5 implements the **L0-L5 agent promotion ladder**, a trust progression system that safely onboards external agents (OpenHands, Hermes, Anthropic SDKs, etc.) by gradually expanding their capabilities while monitoring behavior.

Each level has specific constraints validated against agent executions. Agents can be promoted based on success rate and confidence metrics, or demoted if they violate level constraints.

## Deliverables

### 1. Sandbox Types (`sandbox-lab/sandbox-types.ts`)

**Six sandbox levels:**

| Level | Name | Constraints | Purpose |
|-------|------|-------------|---------|
| **L0** | Dry Run | No tool calls allowed | Observe reasoning quality |
| **L1** | Read-Only | Read files only, no writes | Validate scope discipline |
| **L2** | Simulated | Create patches, no merge | Validate patch quality |
| **L3** | Sandboxed | Execute in container | Validate reliability |
| **L4** | Draft PR | Real branches/PRs, no merge | Final validation |
| **L5** | Trusted | Full autonomy | Proven agent |

**Data structures:**

```typescript
// Agent execution at a level
AgentBehavior {
  agent_id: string,
  level: SandboxLevel,
  execution_time_ms: number,
  tool_calls: number,
  errors: number,
  scope_violations: number,
  test_pass_rate: 0-1,
  confidence_delta: number,
  observations: Record<string, any>,
  passed: boolean
}

// Agent's trust profile
AgentTrustProfile {
  agent_id: string,
  current_level: SandboxLevel,
  promotion_history: { level, date, reason }[],
  total_executions: number,
  successful_executions: number,
  success_rate: 0-1,
  avg_confidence: 0-1,
  risk_score: 0-1,
  approved_for_level: SandboxLevel,
  last_violation?: { date, level, type }
}
```

### 2. Sandbox Validator (`sandbox-lab/sandbox-validator.ts`)

**Validates agent behavior against level constraints.**

**L0 Rules:**
- Must have 0 tool calls (reasoning only)
- Execution time <30s (warn if exceeds)

**L1 Rules:**
- No write attempts allowed
- Must stay within declared scope
- Can read up to 50 files (warn if more)
- Max 2 errors

**L2 Rules:**
- No merge attempts
- No scope violations
- Patches must have >50% test pass rate
- Max 1 error

**L3 Rules:**
- No attempts to modify main branch
- Must have >70% test pass rate
- Max 2 runtime errors
- Execution time <2 minutes

**L4 Rules:**
- No unauthorized merges
- Must have >80% test pass rate
- No scope violations in PR
- Max 3 errors

**L5 Rules:**
- >85% test pass rate (warning only)
- Max 5 errors (warning only)
- No scope violations (warning only)

**Methods:**
- `validate(behavior)` → ValidationResult
- `detectViolations(behavior)` → Violations with severity
- `formatValidation(result)` → Human-readable report

### 3. Promotion Scorer (`sandbox-lab/promotion-scorer.ts`)

**Evaluates agent readiness for promotion to next level.**

**Criteria:**
1. **Execution count** — Min successful runs at current level (default: 3)
2. **Success rate** — ≥80% of executions must pass
3. **Confidence trend** — Average confidence ≥ level's threshold
4. **Recent violations** — None in last 7 days
5. **Error rate** — <2 errors in recent executions
6. **Scope discipline** — 0 scope violations

**Scoring:**
- Base confidence: 0.5
- +0.15 for meeting execution count
- +0.2 for high success rate (≥80%)
- +0.2 for high average confidence
- -0.3 for insufficient executions
- -0.25 for low average confidence
- -0.2 for recent violations
- -0.1 for errors

**Result:**
```typescript
PromotionDecision {
  agent_id: string,
  current_level: SandboxLevel,
  recommended_level: SandboxLevel | 'stay' | 'demote',
  confidence_score: 0-1,
  issues: string[],
  recommendations: string[],
  ready_to_promote: boolean,
  reason: string
}
```

### 4. Sandbox Lab Orchestrator (`sandbox-lab/sandbox-lab.ts`)

**Manages agent trust profiles and promotion lifecycle.**

**Key methods:**
- `registerAgent(agent_id)` — Start agent at L0
- `getProfile(agent_id)` — Retrieve trust profile
- `recordExecution(agent_id, behavior)` — Log execution + auto-promote/demote
- `promoteAgent(agent_id, level, reason)` — Manual promotion
- `resetAgent(agent_id)` — Return to L0 (for testing)
- `listAgents()` — Get all agents
- `getAgentsAtLevel(level)` — Filter by level
- `getStats()` → Lab statistics

**Automatic behavior on execution:**
1. Validate behavior against current level
2. Update success metrics
3. Check for violations → demote if needed
4. Check promotion readiness → promote if eligible (auto-promote enabled)
5. Return validation result + promotion opportunity

**Statistics:**
```typescript
{
  total_agents: number,
  agents_by_level: Record<SandboxLevel, count>,
  avg_success_rate: 0-1,
  avg_confidence: 0-1,
  critical_risk_agents: string[]
}
```

## File Structure

```
chromatic-harness-v2/
├── 02_RUNTIME/
│   ├── sandbox-lab/
│   │   ├── sandbox-types.ts                ✓ (New)
│   │   ├── sandbox-validator.ts            ✓ (New)
│   │   ├── promotion-scorer.ts             ✓ (New)
│   │   └── sandbox-lab.ts                  ✓ (New)
│   │
│   ├── test-phase5.ts                      ✓ (New)
│   └── PHASE_5_COMPLETION_SUMMARY.md       ✓ (This file)
```

## Integration Flow

```
New External Agent (e.g., OpenHands)
        ↓
SandboxLab.registerAgent() → L0
        ↓
Execute with L0 constraints (dry-run)
        ↓
SandboxValidator.validate(behavior)
        ↓
If violations → demote, escalate to human
If no violations → PromotionScorer.evaluate()
        ↓
If ready_to_promote && criteria met:
  SandboxLab.promoteAgent(agent, L1)
        ↓
Execute with L1 constraints (read-only)
        ↓
[Repeat through L2, L3, L4 → eventually L5]
        ↓
L5: Trusted agent, full autonomy
```

## Usage Example

```typescript
const lab = new SandboxLab({
  min_executions_per_level: 3,
  auto_promote: true
});

// Register new agent
lab.registerAgent('openhands-001');

// Execute at L0
const behavior = {
  agent_id: 'openhands-001',
  level: 0,
  execution_time_ms: 5000,
  tool_calls: 0,        // L0: no tools
  errors: 0,
  scope_violations: 0,
  test_pass_rate: 0.95,
  confidence_delta: 0.15,
  observations: {},
  passed: true
};

const result = lab.recordExecution('openhands-001', behavior);
// → { validation_passed: true, promotion_available: false }

// After 3 successful L0 executions:
// Auto-promote to L1 (if enabled)
// Next execution at L1 allows reads but no writes

// Profile after promotion:
const profile = lab.getProfile('openhands-001');
// → { current_level: 1, success_rate: 1.0, avg_confidence: 0.85, ... }
```

## Testing

**Run:**
```bash
npx ts-node 02_RUNTIME/test-phase5.ts
```

**6 comprehensive test cases:**
1. Agent registration and L0 dry-run
2. L0 → L1 promotion workflow
3. L1 read-only validation
4. Promotion scoring
5. Violation detection and auto-demotion
6. Full lifecycle (L0 → L5 progression)

**Expected output:**
```
═══════════════════════════════════════════
Phase 5 Integration Tests
═══════════════════════════════════════════

Test 1: Agent registration and L0 dry-run
  ✓ Agent registered at L0
  ✓ L0 validation passed: true

Test 2: L0 -> L1 Promotion
  ✓ Executions completed: 2
  ✓ Agent promoted to L1

Test 3: L1 Read-only validation
  ✓ L1 read-only validation passed: true
  ✓ L1 write-attempt validation failed: true

Test 4: Promotion scoring
  ✓ Agent has 3 successful executions
  ✓ Ready to promote: true

Test 5: Violation detection and demotion
  ✓ Violation detected: true
  ✓ Agent demoted to L1

Test 6: Full promotion lifecycle (L0 -> L5)
  ✓ Final level: L5
  ✓ Promotion history: 6 milestones

═══════════════════════════════════════════
✓ All Phase 5 tests passed
═══════════════════════════════════════════
```

## Integration Points

### From Phase 4
- ConsoleServer exposes `/agents/:id/profile` endpoint
- Sandbox Lab integration with Console API (optional Phase 5.5)

### To Phase 6 (Frontend)
- Agent dashboard shows promotion history
- Real-time level indicator with risk score
- Violation alerts and demotion notifications

## Safety Features

1. **Behavioral Validation** — Each level has strict constraints
2. **Violation Escalation** — Violations immediately trigger demotion
3. **Gradual Trust** — 6 levels = controlled progression
4. **Audit Trail** — Full promotion history retained
5. **Risk Scoring** — Quantified trust metric (0-1)
6. **Auto-demotion** — Protects against agent regression

## Configuration Options

```typescript
SandboxLabConfig {
  min_executions_per_level: 3,  // Runs before promotion eligible
  confidence_threshold_per_level: {
    0: 0.5, 1: 0.6, 2: 0.7, 3: 0.75, 4: 0.85, 5: 0.9
  },
  error_threshold: 2,           // Errors before demotion
  scope_violation_threshold: 1, // Scope violations before demotion
  auto_promote: true,           // Auto-promote if ready
  audit_trail: true             // Log promotions
}
```

## Known Limitations (Phase 5)

- [ ] No container sandbox enforcement (L3 is policy-only)
- [ ] No real git/PR creation (L4 is simulated)
- [ ] No async constraint checking (e.g., monitoring network activity)
- [ ] No agent-specific training/fine-tuning path
- [ ] No rollback history (only forward history)

## Next: Phase 6 (Frontend Console Dashboard)

Phase 6 builds the React dashboard showing:
- Mission board with real-time status
- Magnet event streams (WebSocket)
- Agent trust profiles and promotion history
- Beads queue with priority sorting
- Gate decision visibility

---

**Phase 5 is READY for Phase 6 dependency-unblock.**
