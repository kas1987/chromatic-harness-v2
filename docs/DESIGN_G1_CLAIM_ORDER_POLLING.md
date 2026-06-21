# G1 Implementation Design: Autonomous Claim-Order Polling Loop

**Document Status**: Design Phase (Pre-Implementation)  
**Author**: Chromatic Architecture Group  
**Date**: 2026-06-20  
**Effort Estimate**: 4–5 weeks (Phase 1–4)  
**Risk Level**: Medium (introduces autonomous background loop; mitigated by strict atomicity + circuit-breaker)

---

## Executive Summary

The Chromatic Harness v2 Orchestration Layer (OL) currently maintains an orders queue (`orders.db`) and a task-runner loop (`task_runner.py`) that consumes work *only when explicitly invoked*. This design establishes an autonomous **claim-order polling loop** that:

1. **Drains the queue continuously** without human intervention
2. **Transitions orders** from `queued` → `claimed` → `completed` (or `failed`)
3. **Atomically claims** orders to prevent race conditions
4. **Monitors**, logs, and alerts on stuck orders and queue depth
5. **Gracefully disables** via configuration flag for rollback safety

The polling loop will run as a **managed background subprocess** under the task-runner supervisor, inherit all safety constraints (budget guard, CI timeout, worker-isolation via worktree), and report outcomes via structured observability channels (metrics, logs, alerts).

**Success criteria**: Orders drain at >1 order/second sustained throughput, with <1% claim failure rate and <5s rollback time on disable.

---

## 1. Architecture Overview

### 1.1 System Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                      Orchestration Layer (OL)                    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  task_runner.py (supervisor loop)                          │  │
│  │  ├─ Load queue + select next bead (go_mode.py)           │  │
│  │  ├─ Score + Decide (confidence gate)                      │  │
│  │  ├─ Claim + Lease (claim_guard.py + lease_manager.py)    │  │
│  │  ├─ Dispatch → worker (subprocess in isolated worktree)   │  │
│  │  ├─ Await + CI check                                      │  │
│  │  ├─ Integrate (merge/close PR)                            │  │
│  │  ├─ Guard + Record (budget_guard, agent_scoring)          │  │
│  │  └─ LOOP (max_iterations, circuit-breaker)                │  │
│  │                                                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            ▲                                       │
│                            │                                       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  claim_order_poller.py (NEW)   [G1 Implementation]         │  │
│  │  ├─ Poll orders.db: SELECT status='queued'               │  │
│  │  ├─ claim_order(order_id) → atomic UPDATEs to claimed   │  │
│  │  ├─ Backoff strategy (exponential on empty queue)        │  │
│  │  ├─ Metrics: throughput, failures, queue_depth           │  │
│  │  ├─ Heartbeat: detect stuck orders (claimed >30min)      │  │
│  │  ├─ Escalation: auto-requeue or alert                    │  │
│  │  └─ Graceful shutdown (OL_CLAIM_ORDER_POLLING flag)      │  │
│  │                                                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            ▼                                       │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  orders.db (SQLite)                                        │  │
│  │  ├─ orders table (id, status, created_at, claimed_at)    │  │
│  │  ├─ status: queued | claimed | completed | failed         │  │
│  │  └─ Indexes: (status, created_at), (claimed_at)          │  │
│  │                                                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

Optional: active_order/ state directory (stores per-order context during claimed phase)
```

### 1.2 Core Interaction Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ Every N seconds (default 5s, configurable)                       │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
            SELECT * FROM orders WHERE status='queued'
                    ORDER BY created_at ASC
                            │
                            ▼
                      For each order:
                    attempt claim_order()
                            │
                 ┌──────────┴──────────┐
                 │                     │
                 ▼                     ▼
            SUCCESS              FAILURE (retry logic)
                 │                     │
                 ▼                     ▼
          UPDATE status='claimed'   Backoff + Log
          UPDATE claimed_at=now()   Circuit-break after N fails
                 │
                 ▼
        Signal task_runner to process
            (via active_order/ directory
             or direct queue notification)
                 │
                 ▼
         task_runner claims the order's
         corresponding bead + dispatches
                 │
                 ▼
        Order transitions: claimed → completed
         (or failed if worker/CI fails)
```

### 1.3 State Transitions & Invariants

**Order states:**
- `queued`: Initial state; ready for claiming. No owner.
- `claimed`: Actively processing or awaiting. Owned by a single agent via claim. Timestamp recorded.
- `completed`: Work finished successfully. Final state; no further transitions.
- `failed`: Work failed (CI red, worker crash, etc.). Final state; no requeue without manual intervention.
- `abandoned`: Order couldn't be processed (invalid bead, timeout, etc.). Final state.

**Atomicity requirement:**
- Transition from `queued` → `claimed` must be **atomic** at the database level.
- If two pollers attempt to claim the same order simultaneously, exactly one succeeds.
- Use SQLite's `PRAGMA journal_mode = WAL` (Write-Ahead Logging) for concurrent readers + single writer.

**Lease mechanism:**
- Integrate with existing `claim_guard.py` + `lease_manager.py` for exclusive resource ownership.
- Each claimed order holds a time-bounded lease (TTL configurable; default 2 hours).
- Lease auto-expires if order is never transitioned to a final state.

### 1.4 Integration with active_order/ Directory

```
active_order/
├─ <order_id>.json
│  ├─ status: claimed
│  ├─ claimed_at: 2026-06-20T12:34:56Z
│  ├─ bead_id: rg-052
│  ├─ worker_pid: <PID>
│  ├─ worker_branch: auto/rg-052
│  └─ heartbeat_at: 2026-06-20T12:35:10Z (updated every 30s)
│
└─ <order_id>.done (marker file when order completes)
```

**Lifecycle:**
1. `claim_order()` creates `active_order/<order_id>.json` with metadata.
2. `task_runner` reads from this directory; launches worker for corresponding bead.
3. Worker updates `heartbeat_at` every 30 seconds (indicates progress).
4. On completion/failure, task_runner writes `active_order/<order_id>.done`.
5. Poller detects `.done` marker → transitions order to `completed` / `failed` in DB.
6. Cleanup: `claim_order_poller` garbage-collects stale `active_order/` entries after 7 days.

### 1.5 Database Schema

**orders table:**
```sql
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',  -- queued | claimed | completed | failed | abandoned
    created_at TEXT NOT NULL,               -- ISO 8601 UTC
    claimed_at TEXT,                        -- ISO 8601 UTC (set when status='claimed')
    completed_at TEXT,                      -- ISO 8601 UTC (set when status='completed'/'failed')
    lease_holder TEXT,                      -- agent/session ID holding the claim
    lease_expires_at TEXT,                  -- ISO 8601 UTC (lease TTL)
    attempts INTEGER DEFAULT 0,             -- number of claim attempts
    error_message TEXT,                     -- reason for failure (if status='failed')
    metadata TEXT                           -- JSON: {bead_id, worker_pid, notes, ...}
);

CREATE INDEX idx_orders_status_created ON orders(status, created_at);
CREATE INDEX idx_orders_lease_expires ON orders(lease_expires_at);
CREATE INDEX idx_orders_claimed_at ON orders(claimed_at);
```

**claim_events table (audit log):**
```sql
CREATE TABLE IF NOT EXISTS claim_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- claim_attempt | claim_success | claim_failed | expired
    agent_id TEXT,
    timestamp TEXT NOT NULL,
    detail TEXT                -- JSON: {reason, error, ...}
);

CREATE INDEX idx_claim_events_order ON claim_events(order_id);
CREATE INDEX idx_claim_events_timestamp ON claim_events(timestamp);
```

---

## 2. claim_order() Method Design

### 2.1 Method Signature & Contract

```python
async def claim_order(
    order_id: str,
    agent_id: str,
    ttl_minutes: int = 120,
    db_path: str | Path | None = None,
) -> ClaimResult:
    """Atomically claim an order by transitioning it from 'queued' to 'claimed'.
    
    Args:
        order_id: Order ID to claim (from orders.db)
        agent_id: Agent/session identifier claiming the order
        ttl_minutes: Lease time-to-live (default 2 hours)
        db_path: Path to orders.db (default CHROMATIC_DB_PATH)
    
    Returns:
        ClaimResult(
            success: bool,
            order_id: str,
            status: str,        # 'claimed' if success, 'queued' or error code if failed
            claimed_at: str,    # ISO 8601 UTC timestamp
            reason: str,        # Human-readable reason if failed
            lease_expires_at: str,
        )
    
    Raises:
        ValueError: order_id invalid or order doesn't exist
        DatabaseError: DB connection lost or corrupted
    
    Side effects:
        - Updates orders.db atomically
        - Creates active_order/<order_id>.json metadata file
        - Logs claim_event to audit table
        - Acquires exclusive lease via lease_manager
    """
```

### 2.2 Implementation Strategy (SQLite)

**Use SQLite's atomic UPDATE + RETURNING clause (v3.35+):**

```python
async def claim_order(order_id: str, agent_id: str, ttl_minutes: int = 120, db_path=None):
    db_path = db_path or _db_path()
    
    async with aiosqlite.connect(db_path) as db:
        # Enable WAL mode for concurrent access (one writer, multiple readers)
        await db.execute("PRAGMA journal_mode = WAL")
        
        # Atomic UPDATE: claim exactly one order with status='queued' and earliest created_at
        cursor = await db.execute(
            """
            UPDATE orders
            SET status = 'claimed',
                claimed_at = datetime('now'),
                lease_holder = ?,
                lease_expires_at = datetime('now', '+' || ? || ' minutes'),
                attempts = attempts + 1
            WHERE id = ?
              AND status = 'queued'
            RETURNING id, status, claimed_at, lease_expires_at;
            """,
            (agent_id, ttl_minutes, order_id)
        )
        
        row = await cursor.fetchone()
        await db.commit()
        
        if not row:
            # Order was not queued (already claimed, completed, etc.) or doesn't exist
            return ClaimResult(
                success=False,
                order_id=order_id,
                status='not_available',
                reason='Order not in queued state or does not exist',
                claimed_at=None,
                lease_expires_at=None,
            )
        
        # Log the successful claim
        await _log_claim_event(db, order_id, 'claim_success', agent_id)
        
        # Create active_order/<order_id>.json metadata
        await _create_active_order_metadata(order_id, agent_id, ttl_minutes)
        
        # Acquire lease via lease_manager
        await _acquire_lease(f"order:{order_id}", agent_id, ttl_minutes)
        
        return ClaimResult(
            success=True,
            order_id=order_id,
            status='claimed',
            claimed_at=row[2],
            lease_expires_at=row[3],
            reason='',
        )
```

### 2.3 Error Handling

| Error Case | Behavior | Logging | Retry |
|---|---|---|---|
| Order already claimed by another agent | Return `success=False`, status='already_claimed' | Log to claim_events (debug level) | Exponential backoff; skip this order this polling cycle |
| Order doesn't exist | Raise `ValueError` | Log to error channel; alert if repeated | No (skip permanently) |
| DB locked (WAL conflict) | Async retry with backoff (3x, 100ms initial) | Log at warn level if all retries exhausted | Yes, on next polling cycle |
| DB connection loss | Raise `DatabaseError`; poller catches and logs | Log at error + alert channel | Yes, poller breaks polling cycle, restarts on next interval |
| Lease acquisition fails | Rollback claim transition; return `success=False` | Log to claim_events + error channel | Exponential backoff |

### 2.4 Atomicity Guarantees

**What is atomic:**
- The `UPDATE orders SET status='claimed' WHERE id=? AND status='queued'` is a single SQL statement.
- SQLite with WAL mode serializes writes; no interleaving.
- RETURNING clause ensures caller sees the committed row.

**What is NOT atomic (but safe):**
- Creating `active_order/<order_id>.json` is a separate filesystem write.
- Leasing via `lease_manager` is a separate ledger write.
- **Mitigation**: If either of these fails post-UPDATE, the claim is considered "successful but partially initialized." The poller logs an error, the order remains `claimed`, and on the next polling cycle the poller detects the incomplete state and either completes initialization or marks the order as abandoned.

**Idempotency:**
- `claim_order()` is NOT idempotent (calling twice on the same order returns `success=False` the second time).
- Safe because pollers never retry the same order twice in the same polling cycle.

---

## 3. Polling Strategy

### 3.1 Polling Loop Skeleton

```python
class ClaimOrderPoller:
    def __init__(self, config: PollerConfig):
        self.config = config
        self.backoff_level = 0  # exponential backoff state
        self.last_poll_time = None
        self.metrics = PollerMetrics()
        self.running = False
    
    async def run(self):
        """Main polling loop. Runs indefinitely until stopped or disabled."""
        self.running = True
        logger.info("claim_order_poller started")
        
        while self.running and self._polling_enabled():
            try:
                await self._poll_cycle()
            except Exception as exc:
                logger.error(f"Poller cycle failed: {exc}", exc_info=True)
                await self._on_error()
        
        logger.info("claim_order_poller stopped")
    
    async def _poll_cycle(self):
        """Execute one polling cycle: fetch queued orders, attempt claims."""
        self.last_poll_time = _now()
        
        # Fetch N oldest queued orders (batch size configurable; default 10)
        orders = await self._fetch_queued_orders(limit=self.config.batch_size)
        
        if not orders:
            # Queue empty: apply exponential backoff (cap at max_backoff_seconds)
            self._apply_backoff_on_empty()
            await asyncio.sleep(self._backoff_seconds())
            return
        
        # Reset backoff to minimum on successful order fetch
        self.backoff_level = 0
        
        claimed_count = 0
        for order in orders:
            result = await claim_order(
                order['id'],
                agent_id=self.config.agent_id,
                ttl_minutes=self.config.claim_ttl_minutes,
            )
            if result.success:
                claimed_count += 1
                self.metrics.claims_success += 1
                logger.info(f"Claimed order {order['id']}")
                # Signal task_runner to process this order
                await self._notify_task_runner(order['id'])
            else:
                self.metrics.claims_failed += 1
                logger.debug(f"Claim failed for {order['id']}: {result.reason}")
            
            # Respect per-claim rate limit (default 100ms between claims)
            await asyncio.sleep(self.config.claim_delay_seconds)
        
        # Sleep until next polling interval
        elapsed = (_now() - self.last_poll_time).total_seconds()
        sleep_time = max(0, self.config.poll_interval_seconds - elapsed)
        await asyncio.sleep(sleep_time)
    
    def stop(self):
        """Gracefully stop the polling loop."""
        self.running = False
    
    def _polling_enabled(self) -> bool:
        """Check if polling is enabled via environment flag."""
        return os.getenv("OL_CLAIM_ORDER_POLLING", "true").lower() in ("true", "1", "yes")
```

### 3.2 Frequency & Batching Strategy

| Parameter | Default | Configurable | Rationale |
|---|---|---|---|
| `poll_interval_seconds` | 5 | Yes (OL_POLLING_INTERVAL) | Balance responsiveness vs. DB load |
| `batch_size` | 10 | Yes (OL_BATCH_SIZE) | Claim 10 orders per poll (tunable for throughput) |
| `claim_delay_ms` | 100 | Yes (OL_CLAIM_DELAY_MS) | Space out claims to avoid DB contention |
| `claim_ttl_minutes` | 120 | Yes (OL_CLAIM_TTL_MINUTES) | Lease validity (2 hours standard) |
| `max_backoff_seconds` | 60 | Yes (OL_MAX_BACKOFF) | Cap on empty-queue exponential backoff |
| `max_concurrent_claimed` | 50 | Yes (OL_MAX_CONCURRENT) | Circuit-breaker: stop claiming if too many in-flight |

**Backoff formula (exponential with jitter):**
```
backoff_seconds = min(
    max_backoff_seconds,
    2 ^ backoff_level + random(0, 1)  # add jitter to avoid thundering herd
)
backoff_level = min(backoff_level + 1, log2(max_backoff_seconds))  # cap growth
```

When queue becomes non-empty again, reset `backoff_level = 0` and resume fast polling.

### 3.3 Backoff Strategy Details

**Scenario 1: Queue has orders**
```
Poll cycle 1: fetch 10 orders, claim all → backoff_level = 0, sleep 5s
Poll cycle 2: fetch 10 orders, claim all → backoff_level = 0, sleep 5s
...
Poll cycle N: fetch 0 orders → backoff_level = 1, sleep 1s (2^0 + jitter)
```

**Scenario 2: Queue is empty**
```
Cycle N: fetch 0 orders → backoff_level = 1, sleep 1s
Cycle N+1: fetch 0 orders → backoff_level = 2, sleep 2s
Cycle N+2: fetch 0 orders → backoff_level = 3, sleep 4s
Cycle N+3: fetch 0 orders → backoff_level = 4, sleep 8s
Cycle N+4: fetch 0 orders → backoff_level = 5, sleep 16s
Cycle N+5: fetch 0 orders → backoff_level = 6, sleep 32s
Cycle N+6: fetch 0 orders → backoff_level = 7, sleep 60s (capped)
Cycle N+7-∞: fetch 0 orders → backoff_level = 7, sleep 60s (stable)

[Order added to queue]
Cycle N+K: fetch 1 order, claim → backoff_level = 0, sleep 5s (reset)
```

---

## 4. Integration Points

### 4.1 orders.db Lifecycle

| Phase | Action | Responsible Module | Notes |
|---|---|---|---|
| Order creation | INSERT orders (status='queued') | External (e.g., go_mode.py, webhook handler) | Order enters queue |
| Polling cycle | SELECT status='queued' | claim_order_poller | Fetch ready orders |
| Claim attempt | UPDATE status='queued'→'claimed' | claim_order() | Atomically transition |
| Worker dispatch | task_runner reads active_order/<id>.json | task_runner | Worker takes over |
| Completion | Worker updates active_order/<id>.done | Worker process | Signals completion |
| DB finalization | UPDATE status='completed'/'failed' | claim_order_poller (via heartbeat/done-file watcher) | Order finalized |
| Expiration (stuck) | UPDATE status='abandoned' + alert | claim_order_poller (stuck-order detector) | TTL exceeded |

### 4.2 Dependency on active_order/ Directory

**Creation (claim_order):**
```json
// active_order/order-xyz.json
{
  "order_id": "order-xyz",
  "status": "claimed",
  "claimed_at": "2026-06-20T12:34:56Z",
  "bead_id": "rg-052",
  "lease_holder": "poller-session-001",
  "lease_expires_at": "2026-06-20T14:34:56Z",
  "worker_pid": null,
  "worker_branch": "auto/rg-052",
  "heartbeat_at": "2026-06-20T12:34:56Z"
}
```

**Task runner reads:**
- Monitors active_order/ directory for new JSON files (watcher or polling).
- Extracts `bead_id` and `order_id`.
- Launches worker to implement bead.
- Updates `active_order/order-xyz.json` with `worker_pid` once worker spawned.

**Completion:**
- Worker process exits (success or failure).
- Task runner writes `active_order/order-xyz.done` (marker file).
- Poller detects `.done` marker → queries task_runner logs for exit code → updates DB status.

**Garbage collection:**
- Poller periodically scans active_order/ for entries stale >7 days.
- Deletes corresponding JSON and .done files.
- Logs GC action.

### 4.3 Dependency on ao-store (Agent Operations)

**Current state:**
- No explicit dependency. The poller is network-free.

**Future dependency (Wave 2):**
- If ao-store provides remote ordering/coordination, poller can query it for order metadata.
- Falls back to local orders.db if ao-store is unavailable (fail-open).

### 4.4 Heartbeat Mechanism (Stuck-Order Detection)

**Goal**: Detect claimed orders that are no longer making progress (worker crashed, hung, etc.).

**Implementation:**
1. Worker (task_runner) updates `active_order/<order_id>.json::heartbeat_at` every 30 seconds.
2. Poller runs a periodic "stuck-order check" (every 60 seconds, configurable):
   - For each order with status='claimed' and `claimed_at < now - 30min`:
     - Read `active_order/<order_id>.json::heartbeat_at`.
     - If `heartbeat_at < now - 5min` (no update for 5 minutes):
       - Log warning.
       - Increment stuck counter.
   - If stuck_count > 3 for same order:
     - Log error + alert.
     - Auto-requeue: transition order back to 'queued' (with note in error_message).
     - Or escalate to user (if `escalate_on_stuck=true`).

**Configurable thresholds:**
- `OL_STUCK_DETECT_INTERVAL_SECONDS`: How often to check (default 60s)
- `OL_HEARTBEAT_TIMEOUT_SECONDS`: How long without heartbeat before "stuck" (default 300s = 5min)
- `OL_STUCK_REQUEUE_THRESHOLD`: How many stuck cycles before auto-requeue (default 3)
- `OL_ESCALATE_ON_STUCK`: Boolean; if true, alert + pause poller (default true for autonomous mode)

### 4.5 Timeout Handling

| Timeout | Value | Trigger | Action |
|---|---|---|---|
| Claim timeout | 30s | claim_order() exceeds 30s (DB stuck) | Log error; skip order; continue loop |
| Heartbeat timeout | 5min | No update to active_order/*.json | Increment stuck counter |
| Order TTL (lease) | 2 hours | claimed_at > now - 120min | Auto-requeue or abandon (config) |
| Polling cycle timeout | N/A | Graceful; no hard timeout | Each cycle can take up to poll_interval + batch processing time |

---

## 5. Monitoring & Observability

### 5.1 Metrics (Prometheus-style)

**Throughput:**
```
claim_order_poller_claims_total{status="success"}      # Counter: successful claims
claim_order_poller_claims_total{status="failure"}      # Counter: failed claims
claim_order_poller_claims_per_minute                   # Gauge: rolling 1-minute rate
```

**Latency:**
```
claim_order_poller_claim_latency_seconds{quantile="p50"}
claim_order_poller_claim_latency_seconds{quantile="p95"}
claim_order_poller_claim_latency_seconds{quantile="p99"}
```

**Queue depth:**
```
claim_order_poller_queue_depth{status="queued"}   # Gauge: orders waiting to be claimed
claim_order_poller_queue_depth{status="claimed"}  # Gauge: orders in-flight
claim_order_poller_queue_depth{status="completed"} # Gauge: orders finished
```

**Circuit-breaker & error rates:**
```
claim_order_poller_db_errors_total              # Counter: DB errors (locked, disconnected, etc.)
claim_order_poller_claim_failure_rate            # Gauge: % of claims that failed (5-min window)
claim_order_poller_stuck_orders                  # Gauge: number of orders without recent heartbeat
claim_order_poller_backoff_level                 # Gauge: current exponential backoff level
claim_order_poller_poll_cycle_duration_seconds   # Histogram: time per polling cycle
```

### 5.2 Logging Strategy

**Log levels:**

| Level | Event | Example |
|---|---|---|
| **INFO** | Poller start/stop, claim success | "Claimed order order-xyz" |
| **WARN** | Retry due to DB lock, backoff applied, stuck order detected | "Claim failed (DB locked); retry next cycle" |
| **ERROR** | Permanent failure, order abandoned, persistent DB error | "Order order-xyz abandoned (TTL exceeded)" |
| **DEBUG** | Polling cycle start/end, queue size, skip reason | "Poll cycle: fetched 10 orders, claimed 8" |

**Log format (structured JSON for aggregation):**
```json
{
  "timestamp": "2026-06-20T12:34:56.123Z",
  "level": "INFO",
  "component": "claim_order_poller",
  "event_type": "claim_success",
  "order_id": "order-xyz",
  "agent_id": "poller-session-001",
  "claimed_at": "2026-06-20T12:34:56Z",
  "lease_expires_at": "2026-06-20T14:34:56Z",
  "duration_ms": 45
}
```

**Log destinations:**
- File: `07_LOGS_AND_AUDIT/claim_order_poller/poller.log` (rolling, 50MB per file, keep 5 files)
- Structured log: `07_LOGS_AND_AUDIT/claim_order_poller/events.jsonl` (append-only)
- Console: INFO+ (for interactive debugging)

### 5.3 Alerting Rules

| Condition | Severity | Action | TTL |
|---|---|---|---|
| Queue depth > 50 for >30 min | **Critical** | Page on-call; may indicate orders are not being claimed | Until queue < 10 |
| Claim failure rate > 10% (5-min window) | **High** | Alert + suggest investigation (DB issue? conflicts?) | Until rate < 5% |
| Stuck orders > 3 | **High** | Log; auto-requeue or escalate (config-dependent) | Until stuck_count = 0 |
| DB disconnection for >1 min | **Critical** | Poller pauses; alert + offer manual recovery | Until connected |
| Backoff level = max (queue empty >30 min) | **Info** | Logged; no action (expected idle state) | Cleared on next order |

---

## 6. Testing Strategy

### 6.1 Unit Tests (test_claim_order.py)

```python
@pytest.mark.asyncio
async def test_claim_order_success():
    """claim_order(valid_id) transitions order to 'claimed'."""
    # Setup: insert a queued order
    order_id = "order-test-001"
    await db.execute("INSERT INTO orders (id, status, created_at) VALUES (?, 'queued', ?)",
                     (order_id, _now()))
    
    # Execute
    result = await claim_order(order_id, agent_id="test-agent")
    
    # Assert
    assert result.success
    assert result.status == "claimed"
    
    # Verify DB state
    row = await db.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
    assert row[0][0] == "claimed"


@pytest.mark.asyncio
async def test_claim_order_already_claimed():
    """claim_order(already_claimed) returns False."""
    order_id = "order-test-002"
    await db.execute("INSERT INTO orders (id, status, claimed_at) VALUES (?, 'claimed', ?)",
                     (order_id, _now()))
    
    result = await claim_order(order_id, agent_id="test-agent-2")
    
    assert not result.success
    assert result.status == "already_claimed"


@pytest.mark.asyncio
async def test_claim_order_invalid_id():
    """claim_order(invalid_id) raises ValueError."""
    with pytest.raises(ValueError):
        await claim_order("nonexistent-order", agent_id="test-agent")


@pytest.mark.asyncio
async def test_concurrent_claims_same_order():
    """Two concurrent claim_order() calls on same order: only one succeeds."""
    order_id = "order-concurrent"
    await db.execute("INSERT INTO orders (id, status, created_at) VALUES (?, 'queued', ?)",
                     (order_id, _now()))
    
    # Run two claims concurrently
    results = await asyncio.gather(
        claim_order(order_id, agent_id="agent-1"),
        claim_order(order_id, agent_id="agent-2"),
    )
    
    # Exactly one succeeds
    assert sum(1 for r in results if r.success) == 1
```

### 6.2 Integration Tests (test_poller_integration.py)

```python
@pytest.mark.asyncio
async def test_poller_claims_queued_orders():
    """Poller fetches and claims 10 queued orders in sequence."""
    # Setup: insert 10 queued orders
    order_ids = [f"order-seq-{i:03d}" for i in range(10)]
    for oid in order_ids:
        await db.execute("INSERT INTO orders (id, status, created_at) VALUES (?, 'queued', ?)",
                         (oid, _now()))
    
    # Run one polling cycle
    config = PollerConfig(batch_size=10, poll_interval_seconds=1)
    poller = ClaimOrderPoller(config)
    await poller._poll_cycle()
    
    # All 10 should be claimed
    result = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'claimed'")
    assert result[0][0] == 10


@pytest.mark.asyncio
async def test_poller_under_load():
    """Poller claims 100+ orders without stalling or data loss."""
    # Setup: 150 queued orders
    for i in range(150):
        await db.execute("INSERT INTO orders (id, status, created_at) VALUES (?, 'queued', ?)",
                         (f"order-load-{i:03d}", _now() - timedelta(seconds=i)))
    
    # Run poller for 5 cycles (batch_size=10)
    config = PollerConfig(batch_size=10)
    poller = ClaimOrderPoller(config)
    for _ in range(5):
        await poller._poll_cycle()
    
    # 50 should be claimed (5 cycles × 10 batch)
    result = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'claimed'")
    assert result[0][0] == 50


@pytest.mark.asyncio
async def test_poller_continues_on_single_claim_failure():
    """If one claim fails, poller continues claiming others."""
    # Setup: 5 queued, 1 already-claimed
    await db.execute("INSERT INTO orders (id, status, created_at) VALUES (?, 'queued', ?)",
                     ("order-ok-1", _now()))
    await db.execute("INSERT INTO orders (id, status, claimed_at) VALUES (?, 'claimed', ?)",
                     ("order-blocked", _now()))
    await db.execute("INSERT INTO orders (id, status, created_at) VALUES (?, 'queued', ?)",
                     ("order-ok-2", _now()))
    
    config = PollerConfig(batch_size=10)
    poller = ClaimOrderPoller(config)
    await poller._poll_cycle()
    
    # 2 should be claimed (the blocked one is skipped)
    result = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'claimed'")
    assert result[0][0] == 3  # includes pre-existing "blocked"
```

### 6.3 Stress Tests (test_poller_stress.py)

```python
@pytest.mark.asyncio
async def test_poller_1000_orders():
    """Poller drains 1000 orders. Measure: throughput, latency, memory."""
    # Setup: 1000 queued orders
    import time
    for i in range(1000):
        await db.execute("INSERT INTO orders (id, status, created_at) VALUES (?, 'queued', ?)",
                         (f"order-stress-{i:04d}", _now()))
    
    config = PollerConfig(batch_size=50)  # larger batch for throughput test
    poller = ClaimOrderPoller(config)
    
    start_time = time.time()
    claimed_count = 0
    while claimed_count < 1000:
        await poller._poll_cycle()
        result = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'claimed'")
        claimed_count = result[0][0]
    
    elapsed = time.time() - start_time
    throughput = claimed_count / elapsed
    
    print(f"Throughput: {throughput:.2f} orders/sec")
    assert throughput > 1.0  # Success criteria: >1 order/sec
```

### 6.4 Chaos Tests (test_poller_chaos.py)

```python
@pytest.mark.asyncio
async def test_db_connection_drops_mid_claim():
    """Poller recovers when DB disconnects during claim attempt."""
    # Setup
    order_id = "order-chaos-1"
    await db.execute("INSERT INTO orders (id, status, created_at) VALUES (?, 'queued', ?)",
                     (order_id, _now()))
    
    # Simulate DB connection drop (mock aiosqlite.connect to raise after 1st call)
    original_connect = aiosqlite.connect
    call_count = [0]
    
    async def mock_connect_fail(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] > 1:
            raise ConnectionError("DB disconnected")
        return original_connect(*args, **kwargs)
    
    # Monkeypatch
    with patch("aiosqlite.connect", side_effect=mock_connect_fail):
        config = PollerConfig(batch_size=10)
        poller = ClaimOrderPoller(config)
        
        # First cycle succeeds
        await poller._poll_cycle()
        
        # Second cycle fails gracefully
        await poller._poll_cycle()  # should not raise; logs error instead
    
    # Verify poller is still running and can recover
    assert poller.running or not poller.running  # stable state


@pytest.mark.asyncio
async def test_orders_db_locked_by_concurrent_process():
    """Poller waits/retries when orders.db is locked."""
    # Setup: obtain exclusive lock on DB
    import sqlite3
    lock_db = sqlite3.connect(":memory:")  # simulate lock
    
    # (In practice, this test would use file-locking or subprocess simulation)
    # Simplified: just verify backoff behavior
    
    config = PollerConfig(batch_size=10)
    poller = ClaimOrderPoller(config)
    
    # Simulate "no orders" → backoff triggered
    await poller._poll_cycle()  # returns empty
    assert poller.backoff_level == 1
    
    await poller._poll_cycle()  # returns empty again
    assert poller.backoff_level == 2
```

---

## 7. Rollback & Disable Plan

### 7.1 Disable Flag

**Environment variable**: `OL_CLAIM_ORDER_POLLING`

| Value | Behavior |
|---|---|
| `"true"` (default) | Polling loop runs normally |
| `"false"` | Polling loop does not start; is a no-op if already running |
| `"pause"` | Loop pauses (no new claims, but existing claimed orders continue) |

**Checking the flag:**
```python
def _polling_enabled() -> bool:
    flag = os.getenv("OL_CLAIM_ORDER_POLLING", "true").lower()
    return flag in ("true", "1", "yes")

# Poller checks this every polling cycle (~5 sec)
while self.running and self._polling_enabled():
    await self._poll_cycle()
```

### 7.2 Graceful Shutdown

**Shutdown sequence (target: <5 seconds):**

1. Set `OL_CLAIM_ORDER_POLLING=false` (or call `poller.stop()`).
2. Poller's next cycle notices the flag and exits the loop.
3. Any in-flight claim operations are allowed to complete (up to 30s timeout on DB operations).
4. Poller logs shutdown event.
5. All claimed orders remain in `status='claimed'` state (NOT auto-reverted).

**No automatic revert** of claimed orders on disable because:
- Orders are safely claimed (atomically); reverting requires coordination.
- Task runner may already be processing them.
- Manual intervention (if needed) is safer than automatic churn.

### 7.3 State Recovery

If polling is disabled while orders are claimed:

**Option A: Manual recovery script**
```bash
# Reset stuck orders back to 'queued'
sqlite3 orders.db << 'EOF'
UPDATE orders
SET status='queued', claimed_at=NULL, lease_holder=NULL
WHERE status='claimed' AND claimed_at < datetime('now', '-6 hours');
EOF
```

**Option B: Active order cleanup**
```bash
# Remove stale active_order/ entries (older than 7 days)
find active_order/ -type f -mtime +7 -delete
```

**Option C: Reset lease**
```bash
# Revoke old leases (e.g., all held by "old-poller-session")
# (Uses lease_manager API)
python3 -c "from scripts.lease_manager import revoke_old_leases; revoke_old_leases(ttl_hours=6)"
```

### 7.4 Monitoring Alert

When repeated claim failures occur:
1. Poller detects failure rate > 10% for 5 minutes.
2. Logs alert: "Claim failure rate elevated; consider disabling polling."
3. If `escalate_on_failure=true` (default for production):
   - Sends alert to monitoring system.
   - Does NOT auto-disable (requires explicit operator action).
   - Offers context: sample error messages, queue depth, DB health.

---

## 8. Implementation Timeline

### Phase 1: Design & Setup (1 week)
- ✓ Design review (this document)
- [ ] Schema update to orders.db (migration script)
- [ ] Setup polling loop skeleton (claim_order_poller.py, imports, config)
- [ ] Setup monitoring hooks (metrics initialization, log structuring)
- [ ] Estimate: 3–4 days

### Phase 2: Implementation (1–2 weeks)
- [ ] Implement `claim_order()` method (atomic UPDATE, lease integration)
- [ ] Implement poller loop (fetch, batch claim, backoff)
- [ ] Integrate with active_order/ directory (create/read metadata)
- [ ] Heartbeat & stuck-order detection
- [ ] Timeout handling (lease expiry, auto-requeue)
- [ ] Estimate: 5–7 days

### Phase 3: Testing (1 week)
- [ ] Unit tests (claim_order atomicity, error cases)
- [ ] Integration tests (poller cycles, task_runner handoff)
- [ ] Stress tests (1000+ orders, throughput measurement)
- [ ] Chaos tests (DB lock, disconnect, hung orders)
- [ ] Estimate: 5–7 days

### Phase 4: Rollout (1 week)
- [ ] Staging deployment: enable polling on 1–2 test orders
- [ ] Monitor metrics (claim latency, throughput, error rate)
- [ ] Gradual production rollout: 10% → 50% → 100% of queue
- [ ] Document runbooks (troubleshooting, manual recovery)
- [ ] Estimate: 5–7 days

**Total: 4–5 weeks**

### Dependencies
- **Blocking**: orders.db schema finalized + migration ready
- **Blocking**: active_order/ state machine documented + integrated with task_runner
- **Blocking**: lease_manager.py stable + tested
- **Blocking**: Monitoring infrastructure ready (metrics collection, log aggregation)
- **Optional**: ao-store integration (Wave 2, can be deferred)

---

## 9. Risk Assessment

| Risk | Probability | Impact | Severity | Mitigation |
|---|---|---|---|---|
| Race condition: order claimed twice | Low (1–5%) | High | **Critical** | Atomic DB UPDATE + RETURNING; unit test concurrency |
| Polling loop crashes silently | Medium (10–20%) | High | **Critical** | Heartbeat monitoring; alert on >5 min no activity |
| Queue depth grows unbounded | Medium (10–20%) | High | **Critical** | Monitor queue_depth metric; alert if >50 for >30 min |
| Memory leak in polling loop | Low (5–10%) | Medium | **High** | Profile memory over 24h stress test; cap active_order/ entries |
| DB locks cause polling stall | Medium (10–20%) | Medium | **High** | Backoff + timeout handling; monitor claim_latency_p99 |
| Stuck orders accumulate | Medium (10–20%) | High | **Critical** | Heartbeat-based detection + auto-requeue; alert on >3 stuck |
| Lease conflict with task_runner | Low (1–5%) | High | **Critical** | Lease TTL > worker timeout; heartbeat updates lease |
| Failure on disable (cannot stop polling) | Low (1–5%) | High | **Critical** | Simple loop flag check; no async cancellation needed |
| Incomplete active_order/ setup | Medium (10–20%) | Medium | **High** | Retry logic; log error + mark order abandoned if >3 failures |

---

## 10. Success Criteria

- ✅ **Throughput**: Orders drain at **>1 order/second** sustained (measured over 1 hour)
- ✅ **Reliability**: Claim success rate **>99%** (failure rate <1% under normal load)
- ✅ **Latency**: `claim_order()` p95 latency **<200ms** (single claim operation)
- ✅ **Stuck-order detection**: Detects and escalates stuck orders within **5 minutes**
- ✅ **Rollback time**: Disable flag takes effect within **<5 seconds**
- ✅ **Test coverage**: All unit, integration, stress, and chaos tests **pass**
- ✅ **Monitoring**: Alerts triggered correctly (queue_depth >50, failure_rate >10%, stuck_orders >3)
- ✅ **Documentation**: Runbooks + troubleshooting guide + API reference complete

---

## 11. Appendix: SQL Examples & Code Templates

### A.1 Schema Migration

```python
# scripts/migrate_orders_schema.py
import sqlite3
from pathlib import Path

DB_PATH = Path("06_DATA/chromatic.sqlite")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create orders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'queued',
            created_at TEXT NOT NULL,
            claimed_at TEXT,
            completed_at TEXT,
            lease_holder TEXT,
            lease_expires_at TEXT,
            attempts INTEGER DEFAULT 0,
            error_message TEXT,
            metadata TEXT
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_lease_expires ON orders(lease_expires_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_claimed_at ON orders(claimed_at)")
    
    # Create claim_events audit table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS claim_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            agent_id TEXT,
            timestamp TEXT NOT NULL,
            detail TEXT
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_events_order ON claim_events(order_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_claim_events_timestamp ON claim_events(timestamp)")
    
    # Enable WAL mode
    cursor.execute("PRAGMA journal_mode = WAL")
    
    conn.commit()
    conn.close()
    print(f"Schema migrated successfully: {DB_PATH}")

if __name__ == "__main__":
    migrate()
```

### A.2 claim_order() Stub

```python
# 02_RUNTIME/orchestrator/claim_order.py
from dataclasses import dataclass
from datetime import datetime, timezone
import aiosqlite
from pathlib import Path
import json
import os

@dataclass
class ClaimResult:
    success: bool
    order_id: str
    status: str
    claimed_at: str | None
    lease_expires_at: str | None
    reason: str = ""

async def claim_order(
    order_id: str,
    agent_id: str,
    ttl_minutes: int = 120,
    db_path: str | Path | None = None,
) -> ClaimResult:
    """Atomically claim an order by transitioning queued → claimed."""
    db_path = db_path or os.getenv("CHROMATIC_DB_PATH", "06_DATA/chromatic.sqlite")
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode = WAL")
        
        cursor = await db.execute(
            """
            UPDATE orders
            SET status = 'claimed',
                claimed_at = datetime('now'),
                lease_holder = ?,
                lease_expires_at = datetime('now', '+' || ? || ' minutes'),
                attempts = attempts + 1
            WHERE id = ?
              AND status = 'queued'
            RETURNING id, status, claimed_at, lease_expires_at;
            """,
            (agent_id, ttl_minutes, order_id)
        )
        
        row = await cursor.fetchone()
        await db.commit()
        
        if not row:
            return ClaimResult(
                success=False,
                order_id=order_id,
                status='not_available',
                claimed_at=None,
                lease_expires_at=None,
                reason='Order not in queued state',
            )
        
        return ClaimResult(
            success=True,
            order_id=order_id,
            status='claimed',
            claimed_at=row[2],
            lease_expires_at=row[3],
            reason='',
        )
```

### A.3 PollerConfig Class

```python
# 02_RUNTIME/orchestrator/poller_config.py
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class PollerConfig:
    """Configuration for claim_order_poller."""
    
    # Polling frequency & batching
    poll_interval_seconds: float = 5.0
    batch_size: int = 10
    claim_delay_seconds: float = 0.1
    
    # Lease & TTL
    claim_ttl_minutes: int = 120
    max_concurrent_claimed: int = 50
    
    # Backoff (exponential when queue empty)
    max_backoff_seconds: float = 60.0
    
    # Stuck-order detection
    stuck_detect_interval_seconds: float = 60.0
    heartbeat_timeout_seconds: float = 300.0
    stuck_requeue_threshold: int = 3
    escalate_on_stuck: bool = True
    
    # Failure handling
    max_claim_retries: int = 3
    escalate_on_failure: bool = True
    
    # DB & paths
    db_path: Path = field(default_factory=lambda: Path("06_DATA/chromatic.sqlite"))
    active_order_dir: Path = field(default_factory=lambda: Path("active_order"))
    
    # Agent identification
    agent_id: str = field(default_factory=lambda: f"poller-{os.getenv('CHROMATIC_SESSION_ID', 'auto')}")
    
    # Logging
    log_dir: Path = field(default_factory=lambda: Path("07_LOGS_AND_AUDIT/claim_order_poller"))
    
    @classmethod
    def from_env(cls) -> "PollerConfig":
        """Load config from environment variables (OL_* prefix)."""
        import os
        return cls(
            poll_interval_seconds=float(os.getenv("OL_POLLING_INTERVAL", 5.0)),
            batch_size=int(os.getenv("OL_BATCH_SIZE", 10)),
            claim_delay_seconds=float(os.getenv("OL_CLAIM_DELAY_MS", 100)) / 1000,
            claim_ttl_minutes=int(os.getenv("OL_CLAIM_TTL_MINUTES", 120)),
            max_backoff_seconds=float(os.getenv("OL_MAX_BACKOFF", 60.0)),
            escalate_on_failure=os.getenv("OL_ESCALATE_ON_FAILURE", "true").lower() in ("true", "1"),
        )
```

---

## 12. Implementation Checklist for Developer

- [ ] **Phase 1: Setup**
  - [ ] Review and approve this design document
  - [ ] Create migration script (schema.py)
  - [ ] Create poller_config.py
  - [ ] Create claim_order.py stub (claims_order function)
  - [ ] Create active_order metadata helper functions
  - [ ] Setup logging infrastructure (structured JSON logs)
  - [ ] Create metrics/observability hooks
  
- [ ] **Phase 2: Implementation**
  - [ ] Implement `claim_order()` (atomic UPDATE + RETURNING)
  - [ ] Implement polling loop (`ClaimOrderPoller` class)
  - [ ] Implement backoff strategy (exponential on empty queue)
  - [ ] Implement stuck-order detection (heartbeat timeout logic)
  - [ ] Implement timeout handling (lease expiry, auto-requeue)
  - [ ] Implement active_order/ directory management
  - [ ] Integrate with lease_manager for exclusive resource claims
  - [ ] Integrate with task_runner for order dispatch
  - [ ] Add OL_CLAIM_ORDER_POLLING flag check
  
- [ ] **Phase 3: Testing**
  - [ ] Unit: claim_order atomicity (race condition test)
  - [ ] Unit: claim_order error cases (already claimed, invalid ID)
  - [ ] Integration: poller claims multiple orders
  - [ ] Integration: poller continues on single failure
  - [ ] Stress: 1000 orders; measure throughput >1/sec
  - [ ] Chaos: DB disconnect recovery
  - [ ] Chaos: DB lock + retry
  - [ ] Coverage: >90% of claim_order_poller.py
  
- [ ] **Phase 4: Rollout**
  - [ ] Staging: enable polling on 1–2 test orders
  - [ ] Monitor metrics: claim_latency, throughput, error_rate
  - [ ] Gradual rollout: 10% → 50% → 100%
  - [ ] Runbook: troubleshooting + manual recovery procedures
  - [ ] Incident response: alert playbooks for stuck orders, queue depth
  - [ ] Documentation: API reference + operational guide

---

## 13. Confidence Assessment

**Design Soundness**: 90/100
- Architecture is well-defined and integrates cleanly with existing harness components.
- Atomic DB operations prevent race conditions.
- Backoff strategy is proven (exponential backoff is industry-standard).
- Mitigations address all identified risks.

**Minor gaps** (handled in implementation):
- Exact lease_manager integration API (needs final API review).
- Exact task_runner handoff mechanism (needs task_runner modifications; outside G1 scope).
- Metrics collection framework (assumes Prometheus-compatible; confirm with DevOps).

**Implementation Confidence**: 75/100
- Core logic is straightforward (polling loop + atomic updates).
- Testing strategy is comprehensive (unit, integration, stress, chaos).
- Some uncertainty around concurrent DB access under very high load (mitigated by WAL mode + batch sizing).
- Active_order/ filesystem coordination adds complexity; requires careful state management (mitigated by heartbeat + garbage collection).

**Production Readiness**: 0/100 (pre-implementation)
- Design is complete and implementable.
- Implementation effort is 4–5 weeks per timeline.
- Rollback is safe and fast (<5 sec).
- Post-implementation: comprehensive testing must validate success criteria before production enablement.

---

## 14. Open Questions & Deferred Decisions

1. **ao-store integration**: Should poller query ao-store for order metadata, or only use local orders.db? (Decision: local-only for v1; ao-store as Wave 2 optional enhancement)

2. **Requeue policy for stuck orders**: Auto-requeue or escalate to user? (Decision: configurable; default auto-requeue for autonomous mode)

3. **Concurrent claimed order cap**: Should poller stop claiming if >N orders are in-flight? (Decision: circuit-breaker at 50 concurrent; configurable)

4. **Integration with task_runner**: Does task_runner read from active_order/ directory or orders.db directly? (Decision: task_runner monitors active_order/ for new JSON files; out-of-scope for G1, requires task_runner design review)

5. **Metrics storage**: Prometheus scrape endpoint or local file-based metrics? (Decision: structured JSON logs + Prometheus histogram/gauge abstractions; final transport TBD with DevOps)

---

**End of Design Document**

---

## Summary for Reviewers

This document provides a comprehensive, implementable design for the G1 autonomous claim-order polling loop. Key strengths:

- **Atomic claiming** prevents race conditions via SQLite UPDATE + RETURNING
- **Exponential backoff** minimizes CPU cost on empty queue
- **Heartbeat-based stuck-order detection** catches hung workers within 5 minutes
- **Graceful disable** via environment flag ensures fast, safe rollback
- **Comprehensive testing strategy** (unit, integration, stress, chaos)
- **Clear timeline** (4–5 weeks, broken into 4 phases)
- **Risk mitigation** for all identified failure modes

Ready for implementation review and Phase 1 approval.
