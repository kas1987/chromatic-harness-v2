# Option C: Chromatic Governance Layer with roach-pi Runtime

## Executive Summary

Chromatic v2 becomes the unified governance and orchestration backbone. roach-pi (and future agents) plugs in as specialized runtime executors. Chromatic's CMP gates, Magnets, and Console wrap all agent workflows regardless of implementation.

**Value proposition:**
- One governance model for all agents (Claude via roach-pi, ChatGPT, Gemini, LangGraph, OpenHands, n8n, Ollama)
- roach-pi keeps its engineering discipline; Chromatic adds multi-agent safety and observability
- Sandbox Lab gates external agents before they access real workflows
- Frontend Console unifies visibility across all runtimes

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    CHROMATIC CONSOLE                         │
│  (React/Frontend: mission queue, Magnet events, dispatch)    │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ (REST / gRPC)
┌─────────────────────────────────────────────────────────────┐
│                      CMP GOVERNANCE                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Intent Magnet → Scope Magnet → Confidence Gate       │   │
│  │ Tool Budget | Permissions | Mission Rules             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ (Mission Packet)
┌─────────────────────────────────────────────────────────────┐
│                    RUNTIME EXECUTOR LAYER                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   roach-pi   │  │  LangGraph   │  │  OpenHands   │ ...  │
│  │   Runtime    │  │   Runtime    │  │   Runtime    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
│  Each runtime is wrapped by:                                 │
│  - Execution Magnet (trace collection)                       │
│  - Cost Magnet (token/budget tracking)                       │
│  - Validation Magnet (test/lint/review hooks)               │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────┐
│               MCP TOOL ABSTRACTION LAYER                     │
│  (File I/O, Repo Access, Browser, API, Database, etc.)      │
│  Single MCP interface; runtimes call via standard tools      │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. CMP Governance Bridge

**Purpose:** Enforce Chromatic policy on any runtime execution.

**Inputs:**
- Mission Packet (from Console or user)
  ```json
  {
    "mission_id": "m-uuid",
    "intent": "Add dark mode to React dashboard",
    "agent_framework": "roach-pi | langraph | openhands",
    "scope": ["src/components/", "styles/"],
    "budget": { "tokens": 50000, "tool_calls": 100 },
    "required_gates": ["intent", "scope", "confidence"],
    "sandbox_level": "L3" // For external agents
  }
  ```

**Process:**
1. **Intent Magnet** — Parse mission clarity, urgency, dependencies
2. **Scope Magnet** — Validate file/repo boundaries
3. **Confidence Gate** — Check if agent capability >= task complexity
4. **CMP Decision** — Approve, escalate, or reject

**Output:** `MissionApproval` or escalation signal

**Implementation location:** `chromatic-harness-v2/02_RUNTIME/cmp-bridge/`

---

### 2. Runtime Executor Wrapper

**Purpose:** Adapt each runtime to Chromatic's execution contract.

**Each runtime gets:**
1. **Runtime Adapter** — Translate Chromatic→Runtime protocol
2. **Execution Magnet** — Inline hook to collect tool calls, errors, retries
3. **Cost Tracker** — Report token usage, tool budget vs. actual
4. **Result Normalizer** — Convert runtime output to Chromatic Beads

**Example: roach-pi adapter**

```typescript
// chromatic-harness-v2/02_RUNTIME/adapters/roach-pi-adapter.ts

class RoachPiAdapter implements RuntimeAdapter {
  async executeMission(packet: MissionPacket): Promise<ExecutionResult> {
    // 1. Convert CMP Mission → roach-pi task
    const roachTask = this.translateMission(packet);

    // 2. Inject Execution Magnet hooks
    const wrapped = this.wrapWithMagnets(roachTask);

    // 3. Run roach-pi workflow
    const roachResult = await roachPi.execute(wrapped);

    // 4. Normalize output to Chromatic format
    const beads = this.toBeads(roachResult);

    // 5. Report to Magnets
    await this.magnets.report({
      stage: 'execution',
      tokens_used: roachResult.tokens,
      tool_calls: roachResult.toolCalls,
      confidence_delta: roachResult.confidence,
      evidence: roachResult.testResults
    });

    return { beads, magnets_report: this.magnets.flush() };
  }
}
```

**Location:** `chromatic-harness-v2/02_RUNTIME/adapters/`

---

### 3. Magnets Integration

**How Magnets hook into runtimes:**

| Magnet | roach-pi Hook | LangGraph Hook | OpenHands Hook |
|--------|---------------|---|---|
| **Execution** | Observe `Agent.beforeToolUse()`, `.afterToolUse()` | Watch LangGraph state transitions | Container exec logging |
| **Cost** | Token counter from `Agent` result | Node invocation token count | API call tracking |
| **Confidence** | Test results + PR review + lint pass | Validation nodes | Sandbox test suite results |
| **Security** | Scan tool args for injection patterns | Validate node inputs | Detect privilege escalation |
| **Validation** | Hook roach-pi's test runner | Trigger validation nodes | Sandbox L5 promoter |

**Implementation:** Each adapter provides a Magnet interface:

```typescript
// chromatic-harness-v2/02_RUNTIME/magnets/execution-magnet.ts

class ExecutionMagnet {
  onToolUse(tool: string, args: Record<string, any>, result: any) {
    // Track what the runtime is doing
    this.log({ tool, args, result, timestamp: Date.now() });
    
    // Detect anomalies (retry storms, permission errors, etc.)
    if (this.isAnomalous(tool, args, result)) {
      this.raiseAlert({ level: 'WARN', message: `Anomaly in ${tool}` });
    }
  }

  onError(error: Error, context: { tool?: string; stage?: string }) {
    // Determine if error is recoverable or should escalate
    const severity = this.classifyError(error);
    this.report({ severity, error: error.message, context });
  }

  report(): MagnetReport {
    return {
      tool_calls: this.toolCalls,
      errors: this.errors,
      anomalies: this.anomalies,
      confidence_delta: this.calculateConfidence()
    };
  }
}
```

**Location:** `chromatic-harness-v2/02_RUNTIME/magnets/`

---

### 4. Beads Bridge (Task Intake)

**Purpose:** Convert runtime outputs → Chromatic Beads (actions, follow-ups, learnings).

**roach-pi → Beads conversion:**

```typescript
// chromatic-harness-v2/02_RUNTIME/beads-bridge.ts

class BeadsBridge {
  async missionToBeads(roachResult: RoachResult): Promise<Bead[]> {
    const beads: Bead[] = [];

    // 1. Closed tasks → Action Beads (if they succeeded)
    for (const task of roachResult.closedTasks) {
      beads.push({
        type: 'action',
        status: 'completed',
        title: task.title,
        evidence: { tests_passed: task.testsPassed, pr_merged: task.prMerged },
        source: { runtime: 'roach-pi', mission_id: roachResult.missionId }
      });
    }

    // 2. Failed/blocked tasks → New Action Beads (follow-up work)
    for (const task of roachResult.blockedTasks) {
      beads.push({
        type: 'action',
        status: 'waiting',
        title: `Follow-up: ${task.blockedOn}`,
        context: { original_task: task.id, blocker: task.blockedOn },
        source: { runtime: 'roach-pi', mission_id: roachResult.missionId }
      });
    }

    // 3. Learnings → Bead memories (for next-session recall)
    for (const learning of roachResult.learnings) {
      beads.push({
        type: 'learning',
        title: learning.title,
        insight: learning.detail,
        tags: learning.tags,
        confidence: learning.confidence
      });
    }

    // 4. Anomalies → Alert Beads
    for (const magnet of roachResult.magnets) {
      if (magnet.anomalies.length > 0) {
        beads.push({
          type: 'alert',
          severity: magnet.anomalies[0].level,
          title: `${magnet.name} detected anomaly`,
          details: magnet.anomalies
        });
      }
    }

    return beads;
  }
}
```

**Location:** `chromatic-harness-v2/02_RUNTIME/beads-bridge.ts`

---

### 5. Sandbox Lab Integration

**Purpose:** Gate external agents (OpenHands, Hermes, future frameworks) before real execution.

**How it integrates with runtimes:**

```
User: "Run external agent OpenHands on code refactor"
                    ↓
        CMP routes to Sandbox Lab (not production)
                    ↓
        L0: Dry run (agent reasoning only, no tools)
        → L1: Read-only (fake files, observe scope discipline)
        → L2: Simulated patch (patch copy only, no merge)
        → L3: Sandboxed container (docker test execution)
        → L4: Draft PR (real branch, no merge)
        → L5: Trusted agent (narrow autonomous work)
                    ↓
        After each level: Magnets score behavior
        Fail at any level → escalate to human review
```

**Implementation:**

```typescript
// chromatic-harness-v2/02_RUNTIME/sandbox-lab.ts

class SandboxLab {
  async promoteLevel(
    agentId: string,
    currentLevel: SandboxLevel,
    evidence: ExecutionReport
  ): Promise<SandboxLevel | 'ESCALATE'> {
    // Score agent behavior at current level
    const passedBehaviorChecks = this.validateBehavior(evidence, currentLevel);
    const confidenceScore = this.magnets.score(evidence);

    if (!passedBehaviorChecks || confidenceScore < 0.7) {
      return 'ESCALATE'; // Stop promotion, notify human
    }

    // Promote to next level if all checks pass
    const nextLevel = this.nextLevel(currentLevel);
    await this.persistPromotion(agentId, nextLevel);
    return nextLevel;
  }
}
```

**Location:** `chromatic-harness-v2/02_RUNTIME/sandbox-lab.ts`

---

### 6. Console REST API

**Purpose:** Expose all Chromatic state to the frontend.

**Key endpoints:**

```typescript
// Endpoints the Console calls

POST   /missions/create                    // Submit new mission
GET    /missions/:id/status                // Check mission progress
GET    /missions/:id/magnets               // Stream magnet events
GET    /beads?status=pending               // View action queue
PATCH  /beads/:id/resolve                  // Mark action done
GET    /sandbox/:agent/promotion-history   // Agent trust tracking
POST   /gates/:id/escalate                 // Human gate override
WS     /missions/:id/events                // WebSocket for real-time updates
```

**Location:** `chromatic-harness-v2/02_RUNTIME/console-api/`

---

## Data Flow Example: Dark Mode PR via roach-pi

```
User: "Add dark mode to React dashboard"
        ↓
    CMP GOVERNANCE LAYER
    • Intent Magnet: "Clear goal, medium complexity" ✓
    • Scope Magnet: "Confined to src/components/" ✓
    • Confidence Gate: "Claude + roach-pi combo = 85%" ✓
    • Approve Mission
        ↓
    ROACH-PI RUNTIME ADAPTER
    • Convert to roach-pi task format
    • Attach Execution Magnet hooks
        ↓
    roach-pi executes:
    1. Task Clarification → [Magnet: Intent clarity scoring]
    2. Planning → [Magnet: Plan quality validation]
    3. Worker Execution → [Magnet: Tool call + cost tracking]
        - Fetch repo files
        - Write CSS + React
        - Commit to branch
    4. Validation → [Magnet: Test results + lint]
    5. PR Review → [Magnet: Confidence delta from review]
        ↓
    MAGNETS SYNTHESIS
    • Execution: 42 tool calls, 120k tokens, 2 retries
    • Cost: Within budget ✓
    • Validation: All tests pass ✓
    • Confidence: 88% (up from 85%)
        ↓
    BEADS BRIDGE
    • Closed task → Action Bead (completed)
    • Learnings → 3 Memory Beads (CSS patterns, component reuse)
    • Confidence gain → Score Bead (evidence for future Claude work)
        ↓
    CONSOLE UPDATE
    • Show PR link
    • Display Magnet summary
    • Offer: "Merge now?" or "Request changes?"
        ↓
    Human review → Merge → Mission closed
```

---

## File Structure

```
chromatic-harness-v2/
├── 00_SOURCE_OF_TRUTH/
│   ├── CHROMATIC_HARNESS_MANIFEST.md
│   ├── DECISION_LOG.md
│   └── OPTION_C_INTEGRATION_ARCHITECTURE.md ← You are here
│
├── 01_PROTOCOLS/
│   ├── CMP_GOVERNANCE_SPEC.md
│   ├── MISSION_PACKET_SCHEMA.json
│   ├── MAGNET_REPORT_SCHEMA.json
│   └── RUNTIME_ADAPTER_INTERFACE.ts
│
├── 02_RUNTIME/
│   ├── adapters/
│   │   ├── roach-pi-adapter.ts          [NEW]
│   │   ├── langraph-adapter.ts
│   │   └── openhands-adapter.ts
│   │
│   ├── magnets/
│   │   ├── execution-magnet.ts          [NEW]
│   │   ├── cost-magnet.ts
│   │   ├── confidence-magnet.ts
│   │   ├── validation-magnet.ts
│   │   ├── security-magnet.ts
│   │   └── magnet-synthesis.ts
│   │
│   ├── cmp-bridge/
│   │   ├── intent-gate.ts               [NEW]
│   │   ├── scope-gate.ts
│   │   ├── confidence-gate.ts
│   │   └── cmp-executor.ts
│   │
│   ├── beads-bridge.ts                  [NEW]
│   ├── sandbox-lab.ts                   [NEW]
│   └── console-api.ts                   [NEW]
│
├── 03_AGENTS/
│   └── (Agent-specific playbooks and configs)
│
├── 04_PLAYBOOKS/
│   └── (Workflow runbooks)
│
├── 05_FRONTEND_CONSOLE/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── MissionBoard.tsx          [NEW]
│   │   │   ├── MagnetDashboard.tsx       [NEW]
│   │   │   └── SandboxPromotions.tsx     [NEW]
│   │   ├── components/
│   │   └── hooks/
│   │
│   └── README.md
│
└── 06_DATA/
    ├── schema.sql
    ├── beads.jsonl
    └── magnets-archive/
```

---

## Implementation Roadmap

### Phase 1: Core Adapter (Week 1)
- [ ] Define `RuntimeAdapter` interface (protocol spec)
- [ ] Build `roach-pi-adapter.ts` (basic execute + result normalization)
- [ ] Implement `Execution Magnet` hook collection
- [ ] Create `MissionPacket` schema

### Phase 2: Magnets Integration (Week 2)
- [ ] Wire Magnets into roach-pi lifecycle
- [ ] Build `Confidence Magnet` (test/lint/review scoring)
- [ ] Implement `Cost Magnet` (token + tool budget tracking)
- [ ] Create `magnet-synthesis.ts` (aggregate reports)

### Phase 3: Governance Bridge (Week 3)
- [ ] Build `CMP Executor` (Intent + Scope + Confidence gates)
- [ ] Create `BeadsBridge` (roach-pi result → action/learning beads)
- [ ] Add escalation logic (human override, policy violations)
- [ ] Implement bead storage in `.beads/issues.jsonl`

### Phase 4: Console API (Week 4)
- [ ] REST API for mission CRUD
- [ ] WebSocket stream for Magnet events
- [ ] Beads endpoint (queue visibility, mark-as-done)
- [ ] Integration tests

### Phase 5: Sandbox Lab (Week 5)
- [ ] L0-L3 implementation (dry-run, read-only, simulated, sandboxed)
- [ ] Agent behavior validator
- [ ] Promotion scorer
- [ ] L4-L5 integration (draft PR, trusted agent)

### Phase 6: Frontend Console (Week 6+)
- [ ] MissionBoard UI (create, status, dispatch)
- [ ] MagnetDashboard (real-time event stream, anomaly detection)
- [ ] SandboxPromotions (agent promotion history, trust level)

---

## Key Decision Points

1. **Data Store for Magnets:** JSONL (like Beads) or DB?
   - **Recommendation:** JSONL for consistency with Beads; adds `magnets-archive.jsonl` in `06_DATA/`

2. **Sync Strategy:** How do roach-pi's git refs + Chromatic's Beads stay in sync?
   - **Recommendation:** Beads Bridge watches for roach-pi PR merge events and creates closed-task beads

3. **roach-pi as Submodule or Dependency?**
   - **Recommendation:** Git submodule in `02_RUNTIME/runtime-engines/roach-pi/` so Chromatic can version-lock it

4. **Console Deployment:** Solo React SPA or integrated into Chromatic harness?
   - **Recommendation:** Separate SPA calling Chromatic Console API; allows independent iteration

5. **Sandbox Lab Scope:** Apply to all agents or only external ones?
   - **Recommendation:** Optional per-mission (`sandbox_level` in Mission Packet); internal roach-pi defaults to L5 (trusted)

---

## Success Criteria

- [ ] **Single governance model:** One CMP for all agents (roach-pi, LangGraph, OpenHands)
- [ ] **Magnet observability:** 8 Magnets each producing normalized event streams
- [ ] **Cross-runtime Beads:** roach-pi tasks, LangGraph outputs, OpenHands results all become comparable Beads
- [ ] **Sandbox Lab proof:** External agent successfully promoted L0→L5 with confidence scoring
- [ ] **Console UX:** User can monitor multiple simultaneous missions across runtimes from one dashboard
- [ ] **roach-pi unchanged:** roach-pi continues to work standalone; Chromatic wraps, doesn't modify

---

## Open Questions

1. Should Magnets store telemetry in `.agents/` (same as beads sync) or a separate DB?
2. How do we handle roach-pi's native validation gates + Chromatic's confidence gates (avoid duplication)?
3. What's the ownership model for Beads created by roach-pi — are they Chromatic Beads or roach-pi issues?
4. Do we version-lock roach-pi to a specific commit in the Sandbox Lab, or promote to latest?
