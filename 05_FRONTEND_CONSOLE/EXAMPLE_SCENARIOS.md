# Claims Dashboard — Example Scenarios & Output

Real-world examples of collision claims detected and resolved by the dashboard.

---

## Scenario 1: Simple Collision (Two Agents, One Bead)

### Setup

Agent A and Agent B both want to claim the same bead.

```
Timeline:
T=0s   Agent A: acquire("queue:bead-001") → GRANTED
T=1s   Agent B: acquire("queue:bead-001") → DENIED (Agent A holds it)
T=5s   Agent A: release("queue:bead-001")
T=6s   Agent B: acquire("queue:bead-001") → GRANTED
```

### Lease State (T=1s, collision present)

**API Response: `/api/claims/state`**

```json
{
  "active_claims": [
    {
      "lease_id": "lease-001-a1b2c3",
      "owner_agent": "agent-orchestrator-001",
      "resources": ["queue:bead-001"],
      "created_at": "2026-06-20T12:00:00Z",
      "expires_at": "2026-06-20T13:00:00Z",
      "heartbeat_at": "2026-06-20T12:00:05Z",
      "status": "active"
    }
  ],
  "stale_claims": [],
  "conflicts": [],
  "deadlock_cycles": [],
  "timestamp": "2026-06-20T12:00:01Z"
}
```

**Dashboard Display:**

```
┌─ Live Collision Claims ● live ───────────────┐
│ Active Claims: 1  │  Stale: 0  │  Conflicts: 0 │
│                                               │
│ ┌─ agent-orchestrator-001 ─────────[Release]─┐
│ │ lease-001-a1b2c3                           │
│ │ Resources: bead-001                        │
│ │ Created: 12:00:00 AM                       │
│ │ Expires in 60m                             │
│ └───────────────────────────────────────────┘
│ No active claims.                           │
└───────────────────────────────────────────┘
```

### When Conflict Appears (T=1.5s)

Both agents try to claim simultaneously:

```json
{
  "active_claims": [
    { "lease_id": "lease-001-a1b2c3", "owner_agent": "agent-orchestrator-001", ... },
    { "lease_id": "lease-002-x9y8z7", "owner_agent": "agent-executor-002", ... }
  ],
  "stale_claims": [],
  "conflicts": [
    {
      "lease_a": "lease-001-a1b2c3",
      "lease_b": "lease-002-x9y8z7",
      "resource": "queue:bead-001",
      "owner_a": "agent-orchestrator-001",
      "owner_b": "agent-executor-002"
    }
  ],
  "deadlock_cycles": [],
  "timestamp": "2026-06-20T12:00:01Z"
}
```

**Dashboard Display:**

```
┌─ Deadlock Detector ───────────────────────┐
│                                           │
│ 1 resource conflict(s):                  │
│                                           │
│ agent-orchestrator-001 ↔ agent-executor-2│
│ Contested: queue:bead-001                │
│                                           │
│ Last updated: 12:00:01 AM                │
└───────────────────────────────────────────┘
```

### After Agent A Releases (T=5s)

Agent A calls `release("queue:bead-001")`. Backend updates status to "released":

```json
{
  "active_claims": [
    {
      "lease_id": "lease-002-x9y8z7",
      "owner_agent": "agent-executor-002",
      "resources": ["queue:bead-001"],
      "created_at": "2026-06-20T12:00:01Z",
      "expires_at": "2026-06-20T13:00:01Z",
      "heartbeat_at": "2026-06-20T12:00:05Z",
      "status": "active"
    }
  ],
  "stale_claims": [],
  "conflicts": [],
  "deadlock_cycles": [],
  "timestamp": "2026-06-20T12:00:05Z"
}
```

**Dashboard Display:** (conflict gone)

```
┌─ Deadlock Detector ───────────────────────┐
│                                           │
│ No deadlocks or conflicts detected.      │
│ ✓ System healthy                          │
│                                           │
│ Last updated: 12:00:05 AM                │
└───────────────────────────────────────────┘
```

---

## Scenario 2: Deadlock Cycle (3-Way Wait)

### Setup

Three agents in circular wait:

```
Agent X: holds bead-1, wants bead-2 (held by Y)
Agent Y: holds bead-2, wants bead-3 (held by Z)
Agent Z: holds bead-3, wants bead-1 (held by X)

Cycle: X → Y → Z → X
```

### Lease State

**Files on disk:** (`state/leases/active_leases.jsonl`)

```jsonl
{"lease_id":"lease-x1","owner_agent":"agent-x","resources":["queue:bead-1"],"status":"active","expires_at":"2026-06-20T13:00:00Z",...}
{"lease_id":"lease-y2","owner_agent":"agent-y","resources":["queue:bead-2"],"status":"active","expires_at":"2026-06-20T13:00:00Z",...}
{"lease_id":"lease-z3","owner_agent":"agent-z","resources":["queue:bead-3"],"status":"active","expires_at":"2026-06-20T13:00:00Z",...}
```

**API Response: `/api/claims/state`**

```json
{
  "active_claims": [
    {"lease_id": "lease-x1", "owner_agent": "agent-x", "resources": ["queue:bead-1"], ...},
    {"lease_id": "lease-y2", "owner_agent": "agent-y", "resources": ["queue:bead-2"], ...},
    {"lease_id": "lease-z3", "owner_agent": "agent-z", "resources": ["queue:bead-3"], ...}
  ],
  "stale_claims": [],
  "conflicts": [
    {"lease_a": "lease-x1", "lease_b": "lease-y2", "resource": "queue:bead-2", ...},
    {"lease_a": "lease-y2", "lease_b": "lease-z3", "resource": "queue:bead-3", ...},
    {"lease_a": "lease-z3", "lease_b": "lease-x1", "resource": "queue:bead-1", ...}
  ],
  "deadlock_cycles": [
    {
      "cycle": ["lease-x1", "lease-y2", "lease-z3"],
      "resources": ["queue:bead-1", "queue:bead-2", "queue:bead-3"],
      "suggested_release": ["lease-x1", "lease-y2", "lease-z3"]
    }
  ],
  "timestamp": "2026-06-20T12:00:00Z"
}
```

**Dashboard Display:**

```
┌─ Live Collision Claims ● live ────────────────┐
│ Active Claims: 3 │ Stale: 0 │ Conflicts: 3    │
│                                              │
│ ┌─ agent-x ────────────────────────[Release]─┐
│ │ lease-x1                                   │
│ │ Resources: bead-1                          │
│ │ Created: 11:59:00 AM (expires in 60m)     │
│ └───────────────────────────────────────────┘
│ ┌─ agent-y ────────────────────────[Release]─┐
│ │ lease-y2                                   │
│ │ Resources: bead-2                          │
│ │ Created: 11:59:30 AM (expires in 60m)     │
│ └───────────────────────────────────────────┘
│ ┌─ agent-z ────────────────────────[Release]─┐
│ │ lease-z3                                   │
│ │ Resources: bead-3                          │
│ │ Created: 11:59:45 AM (expires in 60m)     │
│ └───────────────────────────────────────────┘
│                                              │
└──────────────────────────────────────────────┘

┌─ Deadlock Detector ───────────────────────────┐
│                                              │
│ ⚠ 1 deadlock cycle(s) detected:             │
│                                              │
│ ┌─ Cycle: lease-x1 → lease-y2 → lease-z3 ─┐
│ │ Contested resources:                      │
│ │ • queue:bead-1                            │
│ │ • queue:bead-2                            │
│ │ • queue:bead-3                            │
│ │                                           │
│ │ Suggested release order:                  │
│ │ 1. lease-x1                               │
│ │ 2. lease-y2                               │
│ │ 3. lease-z3                               │
│ └─────────────────────────────────────────┘
│                                              │
└──────────────────────────────────────────────┘
```

### User Action: Force Release Agent X

User clicks "Release" on agent-x's claim. Modal appears:

```
╔═══════════════════════════════════════╗
║ Force Release Claim?                  ║
║                                       ║
║ Lease ID: lease-x1                   ║
║                                       ║
║ ⚠ This will forcibly release the     ║
║ claim. Use only if the owner agent   ║
║ has crashed and is not recovering.   ║
║                                       ║
║ [Yes, Release]    [Cancel]            ║
╚═══════════════════════════════════════╝
```

User clicks "Yes, Release" → Second modal:

```
╔═══════════════════════════════════════╗
║ Confirm Release Claim?                ║
║                                       ║
║ Lease ID: lease-x1                   ║
║                                       ║
║ [Confirm Release]    [Cancel]         ║
╚═══════════════════════════════════════╝
```

User clicks "Confirm Release" → POST `/api/claims/force-release`:

```json
{"lease_id": "lease-x1"}
```

Response:

```json
{
  "status": "released",
  "lease_id": "lease-x1",
  "timestamp": "2026-06-20T12:05:00Z"
}
```

Modal shows success:

```
✓ Claim released successfully.
```

Modal closes, dashboard refreshes. Deadlock is now broken:

**New State:**

```json
{
  "active_claims": [
    {"lease_id": "lease-y2", "owner_agent": "agent-y", "resources": ["queue:bead-2"], ...},
    {"lease_id": "lease-z3", "owner_agent": "agent-z", "resources": ["queue:bead-3"], ...}
  ],
  "stale_claims": [],
  "conflicts": [
    {"lease_a": "lease-y2", "lease_b": "lease-z3", "resource": "queue:bead-3", ...}
  ],
  "deadlock_cycles": [],
  "timestamp": "2026-06-20T12:05:00Z"
}
```

**Dashboard Display:** (cycle gone, one conflict remains)

```
┌─ Deadlock Detector ───────────────────────┐
│                                           │
│ 1 resource conflict(s):                  │
│ agent-y ↔ agent-z                        │
│ Contested: queue:bead-3                  │
│                                           │
│ (No longer a deadlock — Y and Z can      │
│  eventually both finish once Z releases) │
│                                           │
│ Last updated: 12:05:00 AM                │
└───────────────────────────────────────────┘
```

---

## Scenario 3: Stale Claim (Crashed Agent)

### Setup

Agent A claims a bead but crashes without releasing it. No heartbeat renewal.

```
T=0s   Agent A: acquire("queue:bead-work-001") → GRANTED (TTL: 2 hours)
T=5s   Agent A CRASHES → no more heartbeats
T=30m  Claim TTL expires but status still "active" in JSONL
T=30m  Dashboard detects stale claim
```

### At T=30m (After Crash, Stale Claim Detected)

**Lease in file:** Status is still "active" but expires_at is in the past

```json
{
  "lease_id": "lease-a-crashed",
  "owner_agent": "agent-a-crashed",
  "resources": ["queue:bead-work-001"],
  "status": "active",
  "created_at": "2026-06-20T12:00:00Z",
  "expires_at": "2026-06-20T12:30:00Z",
  "heartbeat_at": "2026-06-20T12:00:05Z"
}
```

**API Response:**

```json
{
  "active_claims": [
    {
      "lease_id": "lease-a-crashed",
      "owner_agent": "agent-a-crashed",
      "resources": ["queue:bead-work-001"],
      "created_at": "2026-06-20T12:00:00Z",
      "expires_at": "2026-06-20T12:30:00Z",
      "heartbeat_at": "2026-06-20T12:00:05Z",
      "status": "active"
    }
  ],
  "stale_claims": ["lease-a-crashed"],
  "conflicts": [],
  "deadlock_cycles": [],
  "timestamp": "2026-06-20T12:30:00Z"
}
```

**Dashboard Display:**

```
┌─ Live Collision Claims ● live ────────────────┐
│ Active Claims: 1 │ Stale: 1 │ Conflicts: 0    │
│                                              │
│ ┌─ agent-a-crashed ───────────────[Release]─┐│
│ │ lease-a-crashed  (RED BORDER)              ││
│ │ Resources: bead-work-001                   ││
│ │ Created: 12:00:00 AM                       ││
│ │ ⚠ Stale claim — owner may have crashed    ││
│ │                                            ││
│ └────────────────────────────────────────────┘│
│                                              │
└──────────────────────────────────────────────┘

┌─ Deadlock Detector ───────────────────────┐
│ No deadlocks or conflicts detected.       │
│ (But stale claim above should be released)│
└───────────────────────────────────────────┘
```

### User Force-Releases Stale Claim

User clicks "Release" → confirms twice → POST succeeds.

**New State:**

```json
{
  "active_claims": [],
  "stale_claims": [],
  "conflicts": [],
  "deadlock_cycles": [],
  "timestamp": "2026-06-20T12:30:05Z"
}
```

**Dashboard:**

```
┌─ Live Collision Claims ● live ────────────────┐
│ Active Claims: 0 │ Stale: 0 │ Conflicts: 0    │
│                                              │
│ No active claims.                          │
│                                              │
│ ✓ Claim released successfully.             │
└──────────────────────────────────────────────┘
```

Now other agents can claim the freed resource.

---

## Scenario 4: Hierarchical Resource Conflict

### Setup

Agent A holds `files/data/` (directory), Agent B tries to claim `files/data/secret.key` (file inside).

```
Agent A: acquires with mode="exclusive", resources=["files/data"]
Agent B: tries to acquire, resources=["files/data/secret.key"]
→ Conflict detected (B's resource is hierarchically under A's)
```

### State

```json
{
  "active_claims": [
    {"lease_id": "lease-data-dir", "owner_agent": "agent-data-mover", "resources": ["files/data"], ...},
    {"lease_id": "lease-secret-key", "owner_agent": "agent-crypto", "resources": ["files/data/secret.key"], ...}
  ],
  "stale_claims": [],
  "conflicts": [
    {
      "lease_a": "lease-data-dir",
      "lease_b": "lease-secret-key",
      "resource": "files/data",
      "owner_a": "agent-data-mover",
      "owner_b": "agent-crypto"
    }
  ],
  "deadlock_cycles": [],
  "timestamp": "2026-06-20T12:00:00Z"
}
```

**Dashboard:** Shows that Agent B's fine-grained resource is blocked by Agent A's coarser lock.

---

## Scenario 5: Multiple Beads, Partial Conflicts

### Setup

4 beads, 3 agents with overlapping requests:

```
Agent X: wants beads [bead-1, bead-2]   → GRANTED
Agent Y: wants beads [bead-2, bead-3]   → BLOCKED (conflicts with X on bead-2)
Agent Z: wants beads [bead-3, bead-4]   → GRANTED (no conflict)
```

### State

```json
{
  "active_claims": [
    {"lease_id": "lease-x", "owner_agent": "agent-x", "resources": ["queue:bead-1", "queue:bead-2"], ...},
    {"lease_id": "lease-z", "owner_agent": "agent-z", "resources": ["queue:bead-3", "queue:bead-4"], ...}
  ],
  "stale_claims": [],
  "conflicts": [
    {
      "lease_a": "lease-x",
      "lease_b": "lease-y",
      "resource": "queue:bead-2",
      "owner_a": "agent-x",
      "owner_b": "agent-y"
    }
  ],
  "deadlock_cycles": [],
  "timestamp": "2026-06-20T12:00:00Z"
}
```

**Dashboard:**

```
┌─ Live Collision Claims ───────────────────┐
│ Active Claims: 2 │ Conflicts: 1            │
│                                           │
│ ┌─ agent-x ─────────────────────[Release]─┐
│ │ lease-x                                 │
│ │ Resources: bead-1, bead-2               │
│ │ Created: 12:00:00 AM                    │
│ └───────────────────────────────────────┘
│ ┌─ agent-z ─────────────────────[Release]─┐
│ │ lease-z                                 │
│ │ Resources: bead-3, bead-4               │
│ │ Created: 12:00:02 AM                    │
│ └───────────────────────────────────────┘
└───────────────────────────────────────────┘

┌─ Deadlock Detector ──────────────────────┐
│ 1 resource conflict(s):                 │
│ agent-x ↔ agent-y                       │
│ Contested: queue:bead-2                 │
│                                          │
│ (Note: Agent Y's lease not shown because │
│ it was blocked and not created)         │
└──────────────────────────────────────────┘
```

---

## API Call Examples (cURL)

### 1. Get Current State

```bash
curl -s http://localhost:3000/api/claims/state | jq '.conflicts'
```

Output:
```json
[
  {
    "lease_a": "lease-001",
    "lease_b": "lease-002",
    "resource": "queue:bead-001",
    "owner_a": "agent-a",
    "owner_b": "agent-b"
  }
]
```

### 2. Check for Deadlocks

```bash
curl -s http://localhost:3000/api/claims/state | jq '.deadlock_cycles'
```

Output:
```json
[
  {
    "cycle": ["lease-x1", "lease-y2", "lease-z3"],
    "resources": ["queue:bead-1", "queue:bead-2", "queue:bead-3"],
    "suggested_release": ["lease-x1"]
  }
]
```

### 3. Force Release

```bash
curl -X POST http://localhost:3000/api/claims/force-release \
  -H "Content-Type: application/json" \
  -d '{"lease_id": "lease-001"}'
```

Output:
```json
{
  "status": "released",
  "lease_id": "lease-001",
  "timestamp": "2026-06-20T12:05:00Z"
}
```

### 4. Watch Live Updates (SSE)

```bash
curl -N http://localhost:3000/api/ws/claims?sse=true
```

Output (streaming):
```
data: {"active_claims":[...],"conflicts":[],...}

data: {"active_claims":[...],"conflicts":[{"lease_a":"lease-x","lease_b":"lease-y",...}],...}

data: {"active_claims":[],"conflicts":[],...}
```

---

## Metrics & Indicators

### Health Indicators

| State | Indicator | Color | Action |
|-------|-----------|-------|--------|
| Healthy | No conflicts | Green | Monitor |
| Warning | 1-2 conflicts | Yellow | Watch |
| Alert | Deadlock cycle | Red | Force release |
| Critical | Multiple stale | Red | Force release immediately |

### Timestamps Displayed

- **Created:** When claim was acquired
- **Expires In:** TTL countdown (green if > 10 min, yellow if < 10 min, red if expired)
- **Heartbeat:** When owner last renewed claim (stale if > TTL ago)

---

## Summary

These scenarios demonstrate:
- ✓ Real-time collision detection
- ✓ Deadlock cycle identification
- ✓ Stale claim detection
- ✓ User-friendly force-release workflow
- ✓ Hierarchical resource overlap detection
- ✓ Partial conflict scenarios (some grants, some denials)
- ✓ SSE live updates and polling fallback
- ✓ Clear visual feedback on all states
