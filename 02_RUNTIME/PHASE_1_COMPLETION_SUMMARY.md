# Phase 1 Completion: RuntimeAdapter Interface & Mission Schema

**Completed:** 2026-05-28  
**Issue:** chromatic-harness-v2-lmt

## Summary

Phase 1 establishes the foundational protocol for all runtime executors (roach-pi, LangGraph, OpenHands, etc.) to integrate with the Chromatic Harness governance layer. Any future runtime only needs to implement the `RuntimeAdapter` interface to be compatible.

## Deliverables

### 1. RuntimeAdapter Interface (`01_PROTOCOLS/RUNTIME_ADAPTER_INTERFACE.ts`)

**Core types defined:**
- `MissionPacket` — Input contract (user intent, scope, budget, gates)
- `ExecutionResult` — Output contract (tasks, artifacts, telemetry, learnings, magnet reports)
- `RuntimeAdapter` — Interface all runtimes must implement
- Supporting types: `Task`, `Artifact`, `ToolCall`, `ExecutionError`, `TestResult`, `Learning`, `MagnetReport`, `Anomaly`

**Key adapter methods:**
- `executeMission(packet)` → Runs the mission, returns full execution result
- `validate(packet)` → Checks if mission packet is well-formed
- `canHandle(intent, scope)` → Capability matching for routing
- `capabilities()` → Declares runtime's limits and features
- `shutdown()` → Cleanup resources

**Type safety:** Full TypeScript with JSDoc, no `any` types

### 2. MissionPacket JSON Schema (`01_PROTOCOLS/MISSION_PACKET_SCHEMA.json`)

**Properties:**
- `mission_id` — UUID or `m-*` format
- `intent` — User's goal (10-5000 chars)
- `agent_framework` — roach-pi | langraph | openhands | custom
- `scope` — Array of allowed file paths
- `budget` — tokens + tool_calls + optional wall_time
- `required_gates` — intent | scope | confidence
- `sandbox_level` — 0-5 (L0-L5) for external agents
- `metadata` — Optional context

**Validation:**
- Enforced via JSON Schema (draft-07)
- Runtime validates at accept-time
- 2 example packets provided (code task + external agent sandbox)

### 3. roach-pi Runtime Adapter (`02_RUNTIME/adapters/roach-pi-adapter.ts`)

**Implementation:**
- Extends `RuntimeAdapter` interface
- Translates MissionPacket → roach-pi task format
- Maps CMP gates (intent, scope, confidence) → roach-pi stages
- Collects telemetry via Magnet hooks (stub for Phase 2)
- Normalizes output back to Chromatic ExecutionResult format
- Mock execution for Phase 1 testing

**Key methods:**
- `executeMission()` — Full workflow (validate → translate → wrap → execute → normalize)
- `canHandle()` — Detects code-driven tasks
- `validate()` — Applies schema + runtime-specific rules
- `translateMission()` — Converts MissionPacket → roach-pi format
- `mapGates()` — Gate translation table

**Status:** Functional stub with mock execution; ready for Phase 2 Magnet integration

### 4. Runtime Registry (`02_RUNTIME/runtime-registry.ts`)

**Purpose:**
- Maintains registry of all available runtime adapters
- Factory for instantiation with per-runtime configs
- Routing logic for CMP to find best-fit executor

**Key methods:**
- `initialize()` — Boot all registered runtimes
- `getRuntime(id)` — Lookup by ID
- `listRuntimes()` — Get all registered
- `findBestRuntime(intent, scope)` — Match mission to best handler
- `getCapabilities(id)` — Query runtime limits
- `shutdown()` — Cleanup all

**Configuration:**
- `DEFAULT_REGISTRY_CONFIG` provided with roach-pi
- Extensible pattern for adding LangGraph, OpenHands, etc.

### 5. Integration Test (`02_RUNTIME/test-phase1.ts`)

**Test suite covers:**
1. **MissionPacket validation** — Valid/invalid packet acceptance
2. **Adapter capabilities** — Runtime declares max tokens, supported tools, sandbox level
3. **Mission execution** — Mock execution returns proper result shape
4. **Runtime registry** — Registration, lookup, routing, shutdown

**Run with:**
```bash
npx ts-node 02_RUNTIME/test-phase1.ts
```

**Expected output:** 4 tests pass, all assertions green

## File Structure Created

```
chromatic-harness-v2/
├── 01_PROTOCOLS/
│   ├── RUNTIME_ADAPTER_INTERFACE.ts          ✓ (New)
│   └── MISSION_PACKET_SCHEMA.json             ✓ (New)
│
└── 02_RUNTIME/
    ├── adapters/
    │   └── roach-pi-adapter.ts                ✓ (New)
    ├── runtime-registry.ts                    ✓ (New)
    ├── test-phase1.ts                         ✓ (New)
    └── PHASE_1_COMPLETION_SUMMARY.md          ✓ (This file)
```

## Architecture Checkpoint

The interface now enables this flow:

```
User Intent
    ↓
CMP accepts MissionPacket
    ↓
Runtime Registry routes to best executor (roach-pi, LangGraph, etc.)
    ↓
Adapter.executeMission(packet) runs the work
    ↓
ExecutionResult with telemetry, learnings, magnet reports
    ↓
[Phase 2: Magnets wire into observation points]
[Phase 3: CMP gates enforce governance]
[Phase 4: Console API surfaces results]
```

## Open Questions Resolved

1. **Adapter interface vs. inheritance?** → Interface (composition over inheritance, easier mocking)
2. **roach-pi as submodule?** → Not yet; Phase 1 focuses on wrapper contract
3. **Tool call observability hooks?** → Stubbed in adapter; Phase 2 wires them via Magnets

## Known Limitations (Phase 1)

- [ ] **Mock execution only** — Real roach-pi integration happens in Phase 2
- [ ] **No Magnet hooks wired** — Adapter methods exist but don't call magnets yet
- [ ] **Registry is simple** — No weighting/scoring; just first-match routing
- [ ] **No error recovery** — Doesn't retry failed missions
- [ ] **No logging** — Add `pino` or `winston` in Phase 3

## Next: Phase 2 (Magnets Integration)

Phase 2 wires the Magnets into adapter execution:
1. Execution Magnet hooks into tool calls and errors
2. Cost Magnet tracks token/budget usage
3. Confidence Magnet observes test results and review signals
4. Magnet reports aggregate and score execution

**Acceptance criteria for Phase 2:**
- [ ] All 8 Magnets wire into roach-pi lifecycle
- [ ] Tool calls collected and traced
- [ ] Token budget tracked in real-time
- [ ] Test result scoring working
- [ ] Magnet reports serialized to JSON
- [ ] Integration test includes magnet assertions

## Dependencies

- **Phase 1 → Phase 2:** RuntimeAdapter interface is stable input
- **Phase 1 → Phases 3-6:** No direct dependency; all later phases consume these interfaces

## Testing Status

✓ **Integration tests pass** (test-phase1.ts)
✓ **Type checks pass** (TypeScript strict mode ready)
✓ **Schema validates** (JSON Schema draft-07)

---

**Phase 1 is READY for Phase 2 dependency-unblock.**
