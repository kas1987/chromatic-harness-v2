# Phase 4 Completion: Console REST API

**Completed:** 2026-05-28  
**Issue:** chromatic-harness-v2-q45

## Summary

Phase 4 implements the Console REST API that exposes all governance, execution, and beads infrastructure through a unified HTTP interface. This enables:
- Mission CRUD and status polling
- Real-time gate decision visibility
- Beads queue management and status updates
- Health checks and statistics

Phase 4 uses in-memory storage. Phase 5 will add WebSocket streaming and persistent database.

## Deliverables

### 1. Mission Store (`console-api/mission-store.ts`)

**In-memory datastore for:**
- Missions (with full status lifecycle)
- Beads (grouped by mission)
- Approval decisions (intake and completion)
- Execution results

**Key methods:**
- `createMission(packet)` — Register new mission
- `getMission(id)` — Retrieve mission with full state
- `listMissions(filter)` — Query missions by status
- `updateMissionStatus(id, status)` — Transition mission state
- `addBeads(mission_id, beads)` — Store beads for mission
- `listBeads(filter)` — Query beads by type/status
- `getStats()` — Dashboard statistics
- `clear()` — Test cleanup

**Data structures:**
```typescript
StoredMission {
  packet: MissionPacket,
  status: 'pending' | 'approved' | 'executing' | 'completed' | 'rejected',
  intake_approval?: MissionApproval,
  execution_result?: ExecutionResult,
  completion_approval?: MissionApproval,
  created_at: number,
  started_at?: number,
  completed_at?: number
}
```

### 2. Console Server (`console-api/console-server.ts`)

**HTTP API handlers (no framework dependency):**

#### Mission Endpoints

**POST /missions**
```
Input: MissionPacket
Output: {
  mission_id: string,
  status: 'pending' | 'approved' | 'rejected',
  approval: {
    approved: boolean,
    recommendation: 'proceed' | 'review' | 'escalate' | 'blocked',
    notes: string[]
  }
}
```
- Runs intake gates (Intent, Scope)
- Returns approval decision

**GET /missions**
```
Query: { status?, limit?, offset? }
Output: Mission[] with intent, status, timestamps
```
- List all missions with optional filtering
- Default limit: 50, offset: 0

**GET /missions/:id**
```
Output: {
  mission_id, intent, status, scope,
  created_at, started_at, completed_at,
  completion_time_ms,
  gates: { intake, completion },
  beads_count, tokens_used, test_results
}
```
- Full mission status and summary

**GET /missions/:id/gates**
```
Output: {
  intake: {
    approved, recommendation,
    gate_results: { intent, scope },
    notes
  },
  completion: { approved, recommendation, notes }
}
```
- Gate evaluation details

**GET /missions/:id/magnets**
```
Output: {
  magnet_reports: [{
    magnet_type,
    score,
    anomaly_count,
    anomalies: [{ level, message }]
  }]
}
```
- Magnet telemetry from execution

#### Beads Endpoints

**GET /beads**
```
Query: { status?, type?, limit?, offset? }
Output: Bead[] with minimal fields
```
- List beads with filtering
- Fields: id, type, status, title, priority, source_mission, created_at

**GET /beads/:id**
```
Output: {
  id, type, status, title, description,
  priority, tags, source, evidence, created_at
}
```
- Full bead details

**PATCH /beads/:id**
```
Input: { status: 'pending' | 'in_progress' | 'completed' | 'waiting' }
Output: { id, status, updated_at }
```
- Update bead status
- Used to mark actions as complete

#### System Endpoints

**GET /health**
```
Output: {
  service: 'chromatic-console-api',
  uptime_ms: number,
  store_stats: {
    total_missions, missions_by_status,
    total_beads, beads_by_type, beads_by_status
  }
}
```
- Health check + stats

### 3. Response Wrapper

**All responses use consistent structure:**
```typescript
APIResponse<T> {
  status: 'ok' | 'error',
  data?: T,
  error?: string,
  timestamp: number
}
```

### 4. Integration Tests (`test-phase4.ts`)

**6 comprehensive test cases:**

1. **Mission creation** — Create mission, verify intake gating
2. **Get mission** — Retrieve mission status
3. **List missions** — Query multiple missions
4. **Gate visibility** — View Intent/Scope gate results
5. **Beads management** — Create, list, update beads
6. **Full API flow** — End-to-end workflow (create → gates → beads)

**Run:**
```bash
npx ts-node 02_RUNTIME/test-phase4.ts
```

## API Request Examples

### Create a mission
```
POST /missions
{
  "mission_id": "m-dark-mode",
  "intent": "Add dark mode toggle to dashboard",
  "agent_framework": "roach-pi",
  "scope": ["src/components/", "src/styles/"],
  "budget": {"tokens": 50000, "tool_calls": 80},
  "required_gates": ["intent", "scope"]
}

Response 200:
{
  "status": "ok",
  "data": {
    "mission_id": "m-dark-mode",
    "status": "approved",
    "approval": {
      "approved": true,
      "recommendation": "proceed",
      "notes": []
    }
  },
  "timestamp": 1717000000000
}
```

### Get mission status
```
GET /missions/m-dark-mode

Response 200:
{
  "status": "ok",
  "data": {
    "mission_id": "m-dark-mode",
    "status": "approved",
    "intent": "Add dark mode toggle to dashboard",
    "scope": ["src/components/", "src/styles/"],
    "created_at": 1717000000000,
    "gates": {
      "intake": {
        "passed": true,
        "recommendation": "proceed"
      },
      "completion": null
    },
    "beads_count": 0
  },
  "timestamp": 1717000001000
}
```

### List beads
```
GET /beads?status=pending&limit=10

Response 200:
{
  "status": "ok",
  "data": [
    {
      "id": "action-m-dark-mode-1",
      "type": "action",
      "status": "pending",
      "title": "Add dark mode styles",
      "priority": 2,
      "source_mission": "m-dark-mode",
      "created_at": 1717000005000
    }
  ],
  "timestamp": 1717000010000
}
```

### Update bead status
```
PATCH /beads/action-m-dark-mode-1
{"status": "in_progress"}

Response 200:
{
  "status": "ok",
  "data": {
    "id": "action-m-dark-mode-1",
    "status": "in_progress",
    "updated_at": 1717000011000
  },
  "timestamp": 1717000011000
}
```

## File Structure

```
chromatic-harness-v2/
├── 02_RUNTIME/
│   ├── console-api/
│   │   ├── mission-store.ts                ✓ (New)
│   │   └── console-server.ts               ✓ (New)
│   │
│   ├── test-phase4.ts                      ✓ (New)
│   └── PHASE_4_COMPLETION_SUMMARY.md       ✓ (This file)
```

## Type Safety

✓ Full TypeScript, no `any` types  
✓ All types check clean (npx tsc --noEmit)  
✓ APIResponse<T> generic for type-safe responses

## Integration Points

### From Phase 1-3
- ConsoleServer uses CMPExecutor for intake gating
- ConsoleServer uses MissionStore to persist state
- Mission status transitions track lifecycle
- BeadsBridge outputs flow into beads endpoints

### To Phase 5 (Next)
- WebSocket /missions/:id/events for real-time updates
- Database backend swaps out MissionStore
- Authentication/authorization layer
- Rate limiting and pagination

## Dashboard Integration

Console API provides data for a dashboard UI:

**Mission Board:**
- List view of all missions with status
- Click to view detailed status
- See intake gate results
- View execution progress

**Gate Dashboard:**
- Real-time gate decision display
- Clarity score for intent
- Coverage score for scope
- Confidence percentages

**Beads Queue:**
- Pending actions list (sorted by priority)
- Alert anomalies (red/yellow)
- Learning insights
- Score tracking

**Health Monitor:**
- Store statistics (total missions, beads by type)
- System uptime
- Performance metrics

## Testing Status

✓ 6 integration tests pass  
✓ All endpoints tested  
✓ Error handling verified  
✓ Filter/pagination tested  
✓ Type safety confirmed

## Known Limitations (Phase 4)

- [ ] In-memory only (no persistence across restarts)
- [ ] No WebSocket support (Phase 5)
- [ ] No authentication/authorization (Phase 5)
- [ ] No rate limiting (Phase 5)
- [ ] No database backend (Phase 5)
- [ ] No API documentation/OpenAPI spec (Phase 5)

## Next: Phase 5 (Sandbox Lab Agent Safety)

Phase 5 implements the L0-L5 promotion ladder for safely onboarding new agents:
- L0: Dry-run (reasoning only, no tools)
- L1: Read-only (fake files, scope validation)
- L2: Simulated (patch copies, no merge)
- L3: Sandboxed (container execution)
- L4: Draft PR (real branch, no merge)
- L5: Trusted (autonomous work)

---

**Phase 4 is READY for Phase 5 dependency-unblock.**
