# Collision Claims Dashboard

Real-time collision detection and resolution dashboard for the Chromatic Harness console.

## Overview

The Collision Claims Dashboard monitors exclusive resource claims (leases) across agents and provides:

1. **Live Claim State** — Active leases, owners, resources, expiration times
2. **Deadlock Detection** — Automated cycle detection in resource conflict graphs
3. **Force-Release** — Manual override to release stale or deadlocked claims
4. **Stale Claim Detection** — Identifies expired claims whose owners may have crashed

## Architecture

### Frontend (`src/components/ClaimsCollisionDashboard.tsx`)

React component that:
- Polls `/api/claims/state` every 3 seconds
- Falls back to Server-Sent Events (SSE) at `/api/ws/claims?sse=true` for live updates
- Shows active claims with:
  - Owner agent name
  - Claimed resources (beads)
  - Creation timestamp
  - Expiration countdown
  - Stale indicator (if expired)
- Displays conflict summary and deadlock cycles
- Provides force-release modal with two-step confirmation

### Backend (`src/app/api/claims/`)

#### `/api/claims/state` (GET)

Returns the current collision state:

```typescript
{
  active_claims: [{
    lease_id: string;
    owner_agent: string;
    resources: string[]; // e.g., ["queue:bead-001"]
    created_at: string; // ISO timestamp
    expires_at: string; // ISO timestamp
    heartbeat_at: string; // ISO timestamp
    status: "active" | "released" | "expired";
  }];
  stale_claims: string[]; // lease_ids that are expired
  conflicts: [{
    lease_a: string;
    lease_b: string;
    resource: string; // The contested resource
    owner_a: string;
    owner_b: string;
  }];
  deadlock_cycles: [{
    cycle: string[]; // lease_ids in the cycle
    resources: string[];
    suggested_release: string[]; // Recommended order to release
  }];
  timestamp: string; // ISO timestamp of response
}
```

**Source:** Reads `REPO_ROOT/state/leases/active_leases.jsonl` (JSONL format, one lease per line)

**Conflict Detection Algorithm:**
- Filters to active leases (status="active" and expires_at > now)
- Identifies stale leases (status="active" but expires_at < now)
- Pairwise compares write/exclusive locks for resource overlap
- Supports hierarchical path overlap (e.g., `files/path` ↔ `files/path/subdir`)

**Deadlock Cycle Detection:**
- Builds directed graph of conflicts
- DFS-based cycle detection
- Returns cycles of length > 2
- Suggests release order (cycle nodes in topological order)

#### `/api/claims/force-release` (POST)

Force-releases a claim (sets status to "released"):

**Request:**
```json
{
  "lease_id": "lease-abc123"
}
```

**Response:**
```json
{
  "status": "released" | "not_found" | "error",
  "lease_id": "lease-abc123",
  "timestamp": "2026-06-20T12:34:56Z"
}
```

**Safety:** Updates the JSONL file atomically. Should only be used when:
- Owner agent has crashed and heartbeat is not recovering
- Manual deadlock resolution is needed
- TTL has expired but record is stuck

#### `/api/ws/claims` (GET)

Server-Sent Events (SSE) endpoint for live updates:
- Query param `?sse=true` enables SSE stream
- Sends claim state JSON every 1 second when state changes
- Falls back automatically in frontend (see `useWebSocketClaimsEvents`)

### Conflict Detection

Resource overlap is determined by exact match or hierarchical containment:

```typescript
"queue:bead-001" ↔ "queue:bead-001"     // Exact match → CONFLICT
"files/dir"      ↔ "files/dir/subdir"   // Hierarchy → CONFLICT
"queue:a"        ↔ "queue:b"            // Different → NO CONFLICT
```

### Deadlock Cycles

Detected using DFS on the conflict graph. Example cycle:

```
Agent A holds bead-1, waits for bead-2 (held by B)
Agent B holds bead-2, waits for bead-3 (held by C)
Agent C holds bead-3, waits for bead-1 (held by A)
→ Cycle: A → B → C → A
```

**Suggested Resolution:** Release one lease in the cycle to break it (e.g., release Agent A's claim on bead-1).

## Integration with Lease Manager

The dashboard reads from `scripts/lease_manager.py` and `scripts/claim_guard.py` output:

- **Acquisition:** When an agent claims a bead, `claim_guard.py` creates a lease record
- **Heartbeat:** Agent periodically calls `lease_manager heartbeat --lease-id <id>` to extend TTL
- **Release:** Agent calls `claim_guard.py release --bead <id>` when done
- **Stale Detection:** Dashboard identifies leases where `heartbeat_at + TTL < now`
- **Force Release:** Dashboard can manually set status to "released"

### Lease Record Format

```json
{
  "lease_id": "lease-abc123def456",
  "task_id": "bead-001",
  "owner_agent": "agent-orchestrator",
  "resources": ["queue:bead-001"],
  "mode": "exclusive",
  "risk_tier": "T2",
  "status": "active",
  "created_at": "2026-06-20T12:00:00Z",
  "expires_at": "2026-06-20T13:00:00Z",
  "heartbeat_at": "2026-06-20T12:34:56Z",
  "rollback_plan": "release claim lease",
  "metadata": {"kind": "queue_claim"}
}
```

## Testing

### Unit Tests

**Frontend** (`ClaimsCollisionDashboard.test.tsx`):
- Renders dashboard with active claims
- Shows stale claim warnings
- Detects and displays conflicts
- Shows deadlock cycles
- Force-release confirmation flow
- SSE/polling indicator

**Backend** (`claims/state.test.ts`):
- Returns active claims and conflicts
- Detects stale (expired) leases
- Finds multiple conflicts
- Ignores read-only locks
- Handles missing lease file
- Detects hierarchical path overlap

### Integration Tests

(`__tests__/collision-scenario.integration.test.ts`):

1. **Scenario 1: Collision Detection**
   - Agent A claims bead
   - Agent B tries to claim same bead → denied
   - Dashboard shows conflict

2. **Scenario 2: Sequential Claiming**
   - Agent A claims, holds, releases
   - Agent B then acquires
   - Dashboard shows no conflicts after release

3. **Scenario 3: Deadlock Cycle**
   - Three agents in circular wait
   - Dashboard detects cycle and suggests release order

4. **Scenario 4: Stale Claim Force-Release**
   - Agent A crashes with active claim
   - Dashboard shows stale
   - User force-releases
   - Agent B can then claim

5. **Scenario 5: Complex Multi-Bead Conflicts**
   - 4 beads, 3 agents
   - Some requests blocked, some succeed
   - Dashboard shows correct conflict graph

### Running Tests

```bash
cd 05_FRONTEND_CONSOLE

# Unit tests only
npm test -- ClaimsCollisionDashboard.test.tsx
npm test -- claims/state.test.ts

# All tests (unit + integration)
npm test

# With coverage
npm test -- --coverage
```

## User Guide

### Dashboard Layout

**Left Panel: Live Collision Claims**
- Summary badges (Active, Stale, Conflicts counts)
- List of active claims by owner agent
- Resource names, creation time, expiration countdown
- Red border indicates stale claims
- Yellow border indicates claims expiring in < 5 minutes
- "Release" button per claim → force-release modal

**Right Panel: Deadlock Detector**
- Green message if no deadlocks/conflicts
- Deadlock cycles (if any) with:
  - Cycle path (Agent A → B → C → A)
  - Contested resources
  - Suggested release order (numbered steps)
- Resource conflicts (if no cycles):
  - Agent pair and contested resource

### Force-Release Flow

1. Click "Release" on a claim
2. Confirmation modal appears:
   - Shows lease ID
   - Warning about manual override
   - "Yes, Release" and "Cancel" buttons
3. If user confirms, second modal appears:
   - "Confirm Release" (final gate)
   - "Cancel"
4. On confirmation, POST to `/api/claims/force-release`
5. Dashboard refreshes and shows "✓ Claim released successfully"

**When to use:**
- Owner agent crashed and is not recovering
- Heartbeat stopped but claim not released
- Manual deadlock resolution needed
- **NOT for normal shutdown** (use agent's release logic)

### Monitoring

The dashboard updates automatically:
- **With SSE:** ~1 second latency
- **With polling:** ~3 second latency
- Stale claims show red border once expiry passes
- Conflict count updates in real-time

### Dashboard Indicators

| Indicator | Meaning |
|-----------|---------|
| `● live` | SSE connected, real-time updates |
| `○ polling` | SSE down, 3s polling fallback |
| Red border on claim | Stale (expired, owner may be crashed) |
| Yellow border on claim | Expiring soon (< 5 min to TTL) |
| "Stale: N" badge | N stale claims detected |
| "Live Conflicts: N" badge | N active resource conflicts |

## Integration with Console

The dashboard is integrated into the main console page (`page.tsx`):

```tsx
import ClaimsCollisionDashboard from "@/components/ClaimsCollisionDashboard";

export default function ConsolePage() {
  return (
    <div>
      {/* ... other panels ... */}
      
      {/* Full-width row: Collision Claims Dashboard */}
      <div style={{ marginTop: 16 }}>
        <ClaimsCollisionDashboard />
      </div>
    </div>
  );
}
```

## Performance Considerations

- **Lease file I/O:** Read from disk on each `/api/claims/state` request
- **Conflict detection:** O(n²) pairwise comparison, acceptable for < 100 leases
- **Cycle detection:** DFS with memoization, O(n + edges) per request
- **Update frequency:** 1s SSE or 3s polling (configurable)

For large numbers of leases (> 1000), consider:
- Caching summary in memory with short TTL
- Moving conflict detection to a background worker
- Filtering by risk tier or ownership

## Troubleshooting

### Dashboard shows "Loading claim state..."

**Cause:** `/api/claims/state` not responding

**Fix:**
- Check `REPO_ROOT` env var is set correctly
- Verify `state/leases/active_leases.jsonl` exists and is readable
- Check server logs for 500 errors

### Claims show as stale but are valid

**Cause:** System clock skew or TTL too short

**Fix:**
- Verify system time is correct
- Check `expires_at` in lease record vs current time
- Increase TTL in `claim_guard.py` if needed

### Force-release doesn't work

**Cause:** File permissions or locked file

**Fix:**
- Check write permissions on `state/leases/active_leases.jsonl`
- Ensure no other process is writing to lease file
- Try again after 1-2 seconds

### Deadlock detection missing cycles

**Cause:** Conflict graph incomplete

**Fix:**
- Verify all conflicting leases are in `active_leases.jsonl`
- Check resource names match exactly (case-sensitive)
- Refresh dashboard (Ctrl+R) to reload from disk

## Future Enhancements

- [ ] WebSocket support (currently SSE fallback)
- [ ] Lease history timeline visualization
- [ ] Automatic deadlock resolution (AI-suggested release)
- [ ] Claim priority tiers (P0 preempts P1)
- [ ] Real-time agent status (heartbeat indicator)
- [ ] Claim audit log export
- [ ] Lease monitoring alerts (Slack integration)
- [ ] Resource utilization heatmap

## References

- **Lease Manager:** `scripts/lease_manager.py`
- **Claim Guard:** `scripts/claim_guard.py`
- **Lease Schema:** `schemas/lease.schema.json`
- **Collision Control Spec:** `.beads/issues/OBS-002_enable_file_claim-release_collision_control.md`
