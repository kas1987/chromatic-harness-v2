# Claims Collision API Reference

REST API endpoints for collision claims monitoring and management in the Chromatic console.

## Endpoints

### GET /api/claims/state

Fetch current collision state and conflict analysis.

**Query Parameters:** None

**Response:** 200 OK

```typescript
{
  active_claims: Array<{
    lease_id: string;           // Unique lease identifier
    owner_agent: string;        // Agent holding the claim
    resources: string[];        // Claimed resources (e.g., ["queue:bead-001"])
    created_at: string;         // ISO 8601 timestamp when claim was created
    expires_at: string;         // ISO 8601 timestamp when claim expires
    heartbeat_at: string;       // ISO 8601 timestamp of last heartbeat
    status: "active" | "released" | "expired";
  }>;
  stale_claims: string[];       // Array of lease_ids with expired TTL
  conflicts: Array<{
    lease_a: string;            // First lease_id in conflict
    lease_b: string;            // Second lease_id in conflict
    resource: string;           // Resource causing conflict
    owner_a: string;            // Owner of lease_a
    owner_b: string;            // Owner of lease_b
  }>;
  deadlock_cycles: Array<{
    cycle: string[];            // Ordered lease_ids forming cycle
    resources: string[];        // Resources involved in cycle
    suggested_release: string[]; // Recommended release order
  }>;
  timestamp: string;            // ISO 8601 response timestamp
}
```

**Error Response:** 500 Internal Server Error

```json
{
  "active_claims": [],
  "stale_claims": [],
  "conflicts": [],
  "deadlock_cycles": [],
  "timestamp": "2026-06-20T12:34:56Z",
  "error": "Error message"
}
```

**Example:**

```bash
curl http://localhost:3000/api/claims/state
```

**Response:**

```json
{
  "active_claims": [
    {
      "lease_id": "lease-abc123",
      "owner_agent": "agent-orchestrator",
      "resources": ["queue:bead-001"],
      "created_at": "2026-06-20T12:00:00Z",
      "expires_at": "2026-06-20T13:00:00Z",
      "heartbeat_at": "2026-06-20T12:30:00Z",
      "status": "active"
    }
  ],
  "stale_claims": [],
  "conflicts": [],
  "deadlock_cycles": [],
  "timestamp": "2026-06-20T12:34:56Z"
}
```

---

### POST /api/claims/force-release

Manually release a claim (force-release stale or deadlocked leases).

**Content-Type:** application/json

**Request Body:**

```json
{
  "lease_id": "lease-abc123"
}
```

**Response:** 200 OK

```json
{
  "status": "released",
  "lease_id": "lease-abc123",
  "timestamp": "2026-06-20T12:34:56Z"
}
```

**Error Response:** 404 Not Found

```json
{
  "status": "not_found",
  "lease_id": "lease-abc123"
}
```

**Error Response:** 400 Bad Request

```json
{
  "status": "error",
  "error": "lease_id required"
}
```

**Error Response:** 500 Internal Server Error

```json
{
  "status": "error",
  "error": "Error message"
}
```

**Example:**

```bash
curl -X POST http://localhost:3000/api/claims/force-release \
  -H "Content-Type: application/json" \
  -d '{"lease_id": "lease-abc123"}'
```

**Response:**

```json
{
  "status": "released",
  "lease_id": "lease-abc123",
  "timestamp": "2026-06-20T12:34:56Z"
}
```

---

### GET /api/ws/claims

Server-Sent Events (SSE) endpoint for live claim updates.

**Query Parameters:**
- `sse=true` — Enable SSE mode (required)

**Response:** 200 OK with Content-Type: text/event-stream

**Message Format:** Server-Sent Events (SSE)

Each message is a JSON object matching `/api/claims/state` response:

```
data: {"active_claims":[...],"conflicts":[],...}\n\n
```

**Update Frequency:** 1 second (or when state changes, whichever is faster)

**Example (JavaScript):**

```typescript
const eventSource = new EventSource("/api/ws/claims?sse=true");

eventSource.onmessage = (event) => {
  const state = JSON.parse(event.data);
  console.log("Claims state:", state);
};

eventSource.onerror = () => {
  console.error("SSE connection lost");
  eventSource.close();
};
```

**Example (curl):**

```bash
curl http://localhost:3000/api/ws/claims?sse=true
```

Output:

```
data: {"active_claims":[...],"conflicts":[],...}

data: {"active_claims":[...],"conflicts":[...],...}

...
```

---

## Data Structures

### Lease Record

Full structure of a lease in `state/leases/active_leases.jsonl`:

```typescript
interface LeaseRecord {
  lease_id: string;              // Unique ID: "lease-{12-char hex}"
  task_id: string;               // Associated task (e.g., bead ID)
  owner_agent: string;           // Agent holding the lease
  resources: string[];           // Resources held (e.g., ["queue:bead-001"])
  mode: "read" | "write" | "exclusive" | "verify";
  risk_tier: "T0" | "T1" | "T2" | "T3" | "T4";
  status: "active" | "released" | "expired";
  created_at: string;            // ISO 8601
  expires_at: string;            // ISO 8601
  heartbeat_at: string;          // ISO 8601 (last renewal)
  released_at?: string;          // ISO 8601 (when released, if status="released")
  rollback_plan: string;         // Rollback procedure if claim fails
  metadata: Record<string, any>; // Extended metadata (e.g., {"kind": "queue_claim"})
}
```

### Conflict Pair

Represents two leases competing for the same resource:

```typescript
interface ConflictPair {
  lease_a: string;    // First lease ID
  lease_b: string;    // Second lease ID
  resource: string;   // Contested resource name
  owner_a: string;    // Owner of lease_a
  owner_b: string;    // Owner of lease_b
}
```

### Deadlock Cycle

Circular wait dependency:

```typescript
interface DeadlockCycle {
  cycle: string[];            // Ordered lease IDs in cycle [A, B, C, A...]
  resources: string[];        // Resources involved in cycle
  suggested_release: string[]; // Recommended order to release leases
}
```

---

## Common Patterns

### Polling for Changes

```typescript
async function pollClaimsState() {
  const response = await fetch('/api/claims/state');
  const state = await response.json();
  
  if (state.conflicts.length > 0) {
    console.log(`${state.conflicts.length} conflicts detected`);
  }
  if (state.deadlock_cycles.length > 0) {
    console.log(`${state.deadlock_cycles.length} deadlock cycles detected`);
  }
  if (state.stale_claims.length > 0) {
    console.log(`${state.stale_claims.length} stale claims`);
  }
}

// Poll every 3 seconds
setInterval(pollClaimsState, 3000);
```

### Live Updates via SSE

```typescript
const eventSource = new EventSource('/api/ws/claims?sse=true');

eventSource.addEventListener('message', (event) => {
  const state = JSON.parse(event.data);
  
  // Update UI with latest state
  updateDashboard(state);
  
  // Alert on new deadlocks
  if (state.deadlock_cycles.length > 0) {
    sendAlert(`Deadlock detected: ${state.deadlock_cycles[0].cycle.join(' → ')}`);
  }
});

eventSource.addEventListener('error', () => {
  console.error('SSE connection lost, falling back to polling');
  eventSource.close();
  // Switch to polling fallback
});
```

### Force-Release with Confirmation

```typescript
async function forceReleaseClaim(leaseId: string): Promise<boolean> {
  // Confirm with user
  if (!confirm(`Force release ${leaseId}? This cannot be undone.`)) {
    return false;
  }

  // Send request
  const response = await fetch('/api/claims/force-release', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lease_id: leaseId }),
  });

  if (response.ok) {
    const result = await response.json();
    console.log(`Released: ${result.lease_id}`);
    return true;
  } else if (response.status === 404) {
    console.error('Lease not found');
    return false;
  } else {
    console.error('Force release failed');
    return false;
  }
}
```

### Detect and Handle Deadlocks

```typescript
async function checkForDeadlock(): Promise<void> {
  const response = await fetch('/api/claims/state');
  const state = await response.json();

  for (const cycle of state.deadlock_cycles) {
    console.error(`Deadlock cycle detected: ${cycle.cycle.join(' → ')}`);
    console.log(`Suggested resolution: Release ${cycle.suggested_release[0]}`);

    // Auto-resolve if configured
    if (AUTO_RESOLVE_DEADLOCKS) {
      const leaseToRelease = cycle.suggested_release[0];
      await forceReleaseClaim(leaseToRelease);
    }
  }
}
```

### Monitor Stale Claims

```typescript
async function monitorStaleClaims(): Promise<void> {
  const response = await fetch('/api/claims/state');
  const state = await response.json();

  for (const leaseId of state.stale_claims) {
    const claim = state.active_claims.find(c => c.lease_id === leaseId);
    if (!claim) continue;

    const age = Date.now() - new Date(claim.heartbeat_at).getTime();
    console.warn(`Stale claim: ${claim.owner_agent} (${(age / 60000).toFixed(0)}m old)`);

    // Alert if very old (> 30 min)
    if (age > 30 * 60 * 1000) {
      await forceReleaseClaim(leaseId);
    }
  }
}
```

---

## HTTP Status Codes

| Code | Meaning | Notes |
|------|---------|-------|
| 200 | OK | Request succeeded |
| 400 | Bad Request | Missing or invalid parameters |
| 404 | Not Found | Lease ID not found or already released |
| 500 | Internal Server Error | Server error, check logs |

---

## Rate Limiting

No rate limiting is implemented. For production deployments, consider:
- Max 10 requests/second per IP
- Max 100 concurrent SSE connections
- Cache `/api/claims/state` response for 100ms

---

## Error Handling

Always check response status before parsing JSON:

```typescript
async function claimsApiCall(endpoint: string, method = 'GET', body?: any) {
  try {
    const response = await fetch(endpoint, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(error.error || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (err) {
    console.error(`API call failed: ${err}`);
    throw err;
  }
}
```

---

## Testing

### cURL Examples

```bash
# Get current state
curl http://localhost:3000/api/claims/state | jq

# Force release a claim
curl -X POST http://localhost:3000/api/claims/force-release \
  -H "Content-Type: application/json" \
  -d '{"lease_id":"lease-abc123"}' | jq

# Watch SSE stream
curl http://localhost:3000/api/ws/claims?sse=true
```

### JavaScript/TypeScript Testing

See test files:
- `src/components/ClaimsCollisionDashboard.test.tsx`
- `src/app/api/claims/state.test.ts`
- `src/__tests__/collision-scenario.integration.test.ts`

Run tests:

```bash
npm test
```

---

## Changelog

### v1.0.0 (2026-06-20)

- Initial release
- `/api/claims/state` — Query collision state
- `/api/claims/force-release` — Manual claim release
- `/api/ws/claims` — SSE live updates
- Conflict detection (pairwise resource overlap)
- Deadlock cycle detection (DFS-based)
- Stale claim detection (TTL expiry)
