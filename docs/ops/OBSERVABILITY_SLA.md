# Chromatic Harness v2 — Observability SLA

**Version:** 1.0  
**Effective Date:** 2026-06-20  
**Status:** Production-Ready  
**Owner:** Infrastructure & Observability Team  

---

## Executive Summary

This SLA defines measurable performance baselines, operational capacity limits, and alert thresholds for the Chromatic Harness production runtime. It establishes the contract between operations teams and service consumers for predictable, observable behavior under load.

**Key Commitment:** 95th percentile E2E mission latency <2 seconds under bounded load.

---

## 1. Performance Baselines

### 1.1 Latency Targets (p50 / p95 / p99)

| Component | p50 | p95 | p99 | Notes |
|-----------|-----|-----|-----|-------|
| **Mission Creation** (intake gate) | 50ms | 150ms | 300ms | JSON parse + intent validation |
| **Router Decision** (call_type → model) | 30ms | 100ms | 250ms | Routing table lookup + override check |
| **Magnet Synthesis** (normalize + correlate + score) | 100ms | 500ms | 1200ms | Includes all 6-stage pipeline |
| **CMP Gate Evaluation** (all 3 gates) | 40ms | 120ms | 300ms | Intent + Scope + Confidence gates |
| **Mission Execution Dispatch** | 60ms | 200ms | 400ms | Agent invoke + tool routing |
| **E2E Bounded Mission** (create → approval → result) | 800ms | 1800ms | 2500ms | Full lifecycle, <2 concurrent ops |
| **E2E Unbounded Mission** (scaled load) | 1200ms | 3500ms | 5000ms | High concurrency, queued agents |

**Baseline Conditions:**
- Local Ollama available (LLM inference baseline).
- 0 network jitter, stable CPU/memory allocation.
- Isolated test harness (no production workload).
- Single mission in flight.

**Scaling Rule:** Latencies increase sub-linearly with concurrent missions (up to capacity). See Section 2.2.

---

### 1.2 Throughput Baseline

| Metric | Value | Notes |
|--------|-------|-------|
| **Missions/second (sustained)** | 5–10 | Depends on magnet synthesis load |
| **Router decisions/second** | 100–200 | Call_type lookup bounded by I/O |
| **Magnet events/second (per mission)** | 50–100 | Execution + Cost + Confidence magnets |

---

## 2. Capacity Limits

### 2.1 Concurrent Mission Capacity

| Tier | Concurrent Missions | Max Agents | Token Burn (tokens/min) | Notes |
|------|-------------------|-----------|------------------------|-------|
| **Development** | 3 | 2 | 500k | Local dev machine, shared Ollama |
| **Staging** | 15 | 6 | 2M | Containerized Ollama, 4 GPU |
| **Production** | 50+ | 20+ | 5M+ | Distributed agents, multi-node |

**Assumptions:**
- Each mission spawns 0–3 subagents.
- Average mission duration: 5–30 seconds.
- Token budget per mission: 10k–100k (median 30k).

### 2.2 Latency Degradation Under Load

```
Concurrency | p99 Latency | Throughput | Status
           1 |      300ms  |   10 m/s   | GREEN
           5 |      600ms  |   8 m/s    | GREEN
          15 |     1500ms  |   6 m/s    | YELLOW
          30 |     3000ms  |   4 m/s    | YELLOW
          50 |     5000ms  |   2 m/s    | RED
         100 |    10000ms+ |   <1 m/s   | DEAD
```

**Degradation Rule:** p99 latency grows roughly linear with queue depth. Once concurrent missions exceed **30**, alert threshold switches to YELLOW.

### 2.3 Resource Utilization Limits

| Resource | Limit | Alert Threshold | Notes |
|----------|-------|-----------------|-------|
| **CPU (harness + router)** | 80% | 60% | Per-pod/process |
| **Memory (mission store + magnets)** | 4GB | 2.5GB | Unbounded queue risk |
| **Disk I/O (routing log)** | 100 IOPS | 60 IOPS | JSONL append-heavy |
| **GPU (Ollama inference)** | 16GB | 12GB | Ollama container limit |

---

## 3. Alert Thresholds & Escalation

### 3.1 Health Cockpit Severity Levels

```
LEVEL      LATENCY       QUEUE    ACTION                TIMEOUT
──────────────────────────────────────────────────────────────
GREEN      p95 < 200ms   < 5      Normal ops            —
YELLOW     p95 200–500ms 5–15     Warn ops, investigate 10 min
RED        p95 > 500ms   > 15     Page on-call          5 min
CRITICAL   p99 > 2000ms  > 30     Page + exec escalate  2 min
```

**Health Cockpit Logic:**

1. **GREEN** — All checks pass, no alerts.
2. **YELLOW** — Non-blocking warnings (optional service down, stale artifact). Ops notified but no escalation.
3. **RED** — Hard integrity failure or performance SLA breach. **Escalate in 5 minutes if unresolved.**
4. **CRITICAL** — Mission lifecycle broken (e.g., route failures, gate panic). **Immediate exec escalation.**

### 3.2 Metric-Driven Alert Rules

#### Latency Alerts

```python
if p99_latency_ms > 500:
    alert(SEVERITY="page", MESSAGE="P99 latency breach: {p99_latency_ms}ms (SLA <500ms)")
    escalate_after_minutes(5)

if p95_latency_ms > 200:
    alert(SEVERITY="warn", MESSAGE="P95 latency degrading: {p95_latency_ms}ms (baseline 100ms)")
```

#### Queue & Concurrency Alerts

```python
if queue_depth > 30:
    alert(SEVERITY="page", MESSAGE="Mission queue depth {queue_depth} (capacity 50)")

if concurrent_missions > 40:
    alert(SEVERITY="warn", MESSAGE="High concurrency {concurrent_missions}/50, p99 latency {p99}ms")
```

#### Token Burn Alerts

```python
baseline_token_burn = 500_000  # tokens/min
current_burn = measure_token_usage_per_minute()

if current_burn > baseline_token_burn * 2:
    alert(SEVERITY="warn", MESSAGE="Token burn rate 2x baseline: {current_burn}/min")

if current_burn > baseline_token_burn * 3:
    alert(SEVERITY="page", MESSAGE="Token burn rate 3x baseline: {current_burn}/min (cost spike risk)")
```

#### Integrity & Health Alerts

```python
# Routing log stale (no updates >72h)
if routing_log_age_hours > 72:
    alert(SEVERITY="warn", MESSAGE="Routing log stale: {age_hours}h")

# Skill inventory empty
if skill_count == 0:
    alert(SEVERITY="fail", MESSAGE="Skill inventory empty — cannot route")

# Mission store full (memory cap)
if mission_store_memory_gb > 3.5:
    alert(SEVERITY="page", MESSAGE="Mission store near capacity: {mem}GB / 4GB")
```

### 3.3 Cockpit Red Trigger Conditions

The health cockpit transitions to **RED** if **any** of these occur:

- ✗ **Hard integrity failure:** hooks configuration missing, routing_log corrupt, skill_inventory empty.
- ✗ **p99 latency >500ms** for >5 consecutive minutes.
- ✗ **Mission queue depth >30** (capacity breach imminent).
- ✗ **Core service unreachable:** Ollama down, routing layer panicked.
- ✗ **Token burn rate >3x baseline** (runaway cost).
- ✗ **Mission store OOM risk:** >85% memory utilized.

**Escalation Rule:** If cockpit is RED for >5 minutes, page on-call and begin diagnostic runbook.

---

## 4. Observability Instrumentation

### 4.1 Metrics Collection Points

#### Mission Lifecycle

```python
# At mission creation
METRICS['mission_created'] = {
    'mission_id': str,
    'timestamp_utc': str,
    'objective_length': int,
    'agent_role': str,
    'confidence_required': float,
}

# At router decision
METRICS['router_decision'] = {
    'mission_id': str,
    'call_type': str,
    'selected_model': str,
    'decision_latency_ms': int,
    'override_applied': bool,
    'timestamp_utc': str,
}

# At magnet synthesis
METRICS['magnet_synthesis'] = {
    'mission_id': str,
    'collected_count': int,
    'normalized_count': int,
    'confidence_delta': float,
    'risk_delta': float,
    'synthesis_latency_ms': int,
    'timestamp_utc': str,
}

# At CMP gate evaluation
METRICS['cmp_gates'] = {
    'mission_id': str,
    'intent_gate_pass': bool,
    'scope_gate_pass': bool,
    'confidence_gate_pass': bool,
    'overall_approval': bool,
    'gate_latency_ms': int,
    'timestamp_utc': str,
}

# At mission completion
METRICS['mission_completed'] = {
    'mission_id': str,
    'status': str,  # approved | rejected | error
    'total_duration_ms': int,
    'execution_duration_ms': int,
    'token_burn': int,
    'agent_subagent_count': int,
    'timestamp_utc': str,
}
```

#### Performance & Health

```python
# Periodic snapshot
METRICS['cockpit_snapshot'] = {
    'timestamp_utc': str,
    'p50_latency_ms': int,
    'p95_latency_ms': int,
    'p99_latency_ms': int,
    'queue_depth': int,
    'concurrent_missions': int,
    'token_burn_per_min': int,
    'cpu_percent': float,
    'memory_gb': float,
    'disk_io_iops': int,
    'services': {
        'ollama': 'pass' | 'warn' | 'fail',
        'router': 'pass' | 'warn' | 'fail',
        'beads_queue': 'pass' | 'warn' | 'fail',
    }
}
```

### 4.2 Observability Pipeline

```
┌─────────────────────┐
│  Mission Lifecycle  │
│  (create/exec/end)  │
└──────────┬──────────┘
           │ emit metrics
           ↓
┌─────────────────────┐
│  Local Aggregator   │ (ring buffer, sliding window)
│  - latency histo    │
│  - queue depth      │
│  - token burn       │
└──────────┬──────────┘
           │ roll up every 60s
           ↓
┌─────────────────────┐
│  Metrics Sink       │
│  - ERROR_LOG (local)│
│  - Time-series DB   │ (opt. Prometheus / InfluxDB)
└──────────┬──────────┘
           │ trigger rules
           ↓
┌─────────────────────┐
│  Alert Router       │
│  - WARN → logs      │
│  - PAGE → PagerDuty │
│  - EXEC → escalate  │
└─────────────────────┘
```

### 4.3 Logging & Audit Trail

**Mission audit log format (JSONL):**
```json
{
  "timestamp_utc": "2026-06-20T14:22:45.123Z",
  "event_type": "mission_lifecycle",
  "mission_id": "CHR-MISSION-A1B2C3D4",
  "phase": "router_decision",
  "latency_ms": 87,
  "metadata": {
    "call_type": "multi_file_refactor",
    "selected_model": "claude-opus-sonnet",
    "confidence_score": 0.92
  }
}
```

**Health cockpit log format (JSONL):**
```json
{
  "timestamp_utc": "2026-06-20T14:22:45.123Z",
  "event_type": "cockpit_check",
  "overall_status": "yellow",
  "readiness_score": 85,
  "p95_latency_ms": 250,
  "queue_depth": 12,
  "alerts": [
    { "severity": "warn", "message": "p95 latency 250ms (baseline 100ms)" }
  ]
}
```

---

## 5. Operational Dashboards & Views

### 5.1 Real-Time Health Dashboard

**Endpoint:** `GET /health/cockpit`

```json
{
  "timestamp_utc": "2026-06-20T14:22:45Z",
  "overall_status": "green",
  "readiness_score": 98,
  "uptime_hours": 1.5,
  "sla_compliance": {
    "latency": true,
    "throughput": true,
    "capacity": true
  },
  "performance": {
    "p50_latency_ms": 45,
    "p95_latency_ms": 150,
    "p99_latency_ms": 380,
    "throughput_missions_per_sec": 7.2
  },
  "capacity": {
    "concurrent_missions": 8,
    "max_concurrent": 50,
    "queue_depth": 2,
    "token_burn_per_min": 320000
  },
  "services": {
    "ollama": { "status": "pass", "latency_ms": 45 },
    "router": { "status": "pass", "latency_ms": 28 },
    "beads_queue": { "status": "pass", "items_ready": 3 }
  },
  "alerts": []
}
```

### 5.2 Mission Timeline View

Shows a mission's journey through the pipeline with latency markers:

```
Mission: CHR-MISSION-A1B2C3D4
Objective: "Refactor auth middleware"

Timeline (all times in UTC):
├─ 14:22:45.001 CREATED      (0ms)
├─ 14:22:45.051 ROUTER DECISION  (+50ms, model=opus)
├─ 14:22:45.152 MAGNET SYNTHESIS  (+101ms, confidence_delta=+0.15)
├─ 14:22:45.203 INTENT GATE       (+51ms, pass)
├─ 14:22:45.254 SCOPE GATE        (+51ms, pass)
├─ 14:22:45.305 CONFIDENCE GATE   (+51ms, pass, 0.92 >= 0.75)
├─ 14:22:45.368 AGENT DISPATCH    (+63ms, subagents=2)
├─ 14:22:47.523 AGENT EXECUTION   (+2155ms, token_burn=35,000)
├─ 14:22:47.612 RESULT DELIVERY   (+89ms)
└─ 14:22:47.612 COMPLETED         (total E2E: 2611ms)

SLA Status: PASS (E2E <2000ms target met? NO, 2611ms exceeds bounded SLA)
           WARN: High execution latency due to token burn (35k tokens)
```

### 5.3 Quarterly Trend Report

```
Cohort: Last 7 days (2026-06-13 to 2026-06-20)
Missions Completed: 1,234
Success Rate: 98.5%
Avg E2E Latency: 1,240ms (baseline 1,000ms, +24% regression)
p99 Latency: 3,200ms (SLA 2,500ms, BREACH)
Token Burn/Mission: 45,000 (baseline 30,000, +50% inflation)

Trend: Confidence gates increasingly strict (false rejection rate +5%), 
       recommending tuning or learning loop feedback.
```

---

## 6. Runbooks & Response Procedures

### 6.1 Latency SLA Breach (p99 >500ms)

**Detection:** Cockpit alert, Prometheus rule.

**Immediate (0–5 min):**
1. Check mission queue depth: `GET /health/queue`.
2. Identify top-N slowest missions: query `mission_audit.jsonl`, sort by latency.
3. Check Ollama availability: `curl http://127.0.0.1:11434/api/tags`.
4. Check router state: `ls -la routes_*.jsonl`, verify freshness <72h.

**Diagnosis (5–15 min):**
```bash
# Pull last 100 mission latencies
jq '.latency_ms' 07_LOGS_AND_AUDIT/missions/*.jsonl | sort -n | tail -20

# Check for hotspots
jq -s 'group_by(.call_type) | map({type: .[0].call_type, avg_ms: (map(.latency_ms)|add/length)})' ...

# Check magnet synthesis bottleneck
jq '.metadata | select(.phase=="magnet_synthesis") | .latency_ms' ...
```

**Mitigation:**
- ✓ Scale up Ollama GPU if OOM or inference timeout.
- ✓ Reduce concurrent mission limit (temporary).
- ✓ Enable routing log tail sampling (reduce write I/O).
- ✓ Page on-call for deeper investigation if breach persists >5 min.

### 6.2 Mission Queue Depth Spike (>30)

**Detection:** Cockpit alert, automated threshold.

**Immediate:**
1. Measure backlog age: oldest mission timestamp.
2. Check agent availability: `bd ready --json | jq 'length'`.
3. Measure token burn rate: rolling 1-min average.

**Mitigation:**
- ✓ Invoke spillover agents if configured.
- ✓ Reduce max concurrent to 30 (graceful degradation).
- ✓ Page on-call if backlog age >2 minutes.

**Escalation:** If queue grows unbounded (>100), halt mission intake, diagnose deadlock.

### 6.3 Token Burn Rate 3x Baseline

**Detection:** Cockpit alert, billing system.

**Immediate:**
1. Identify high-burn missions: `jq '.metadata | select(.token_burn > 50000)'`.
2. Check for loop/retry conditions (infinite token leak).
3. Assess cost impact: `burn_rate * minutes_elapsed * model_cost_per_token`.

**Mitigation:**
- ✓ Kill high-burn missions if cost unjustifiable.
- ✓ Reduce token budget per mission.
- ✓ Switch to cheaper model for long-running tasks.
- ✓ Page on-call for cost approval if >$100/hr.

### 6.4 Cockpit RED for >5 Minutes

**Automatic Escalation:**

1. Log alert to ERROR_LOG with runbook link.
2. Page on-call via PagerDuty with summary.
3. Begin diagnostic telemetry collection (memory dumps, profile, request traces).
4. Notify billing if cost-related; notify ops if infra-related.

**On-Call Response:**
```
1. Acknowledge page (PagerDuty) → 2 min response SLA.
2. SSH to harness: check live metrics (`harness_health_check.py`).
3. Assess severity: YELLOW/RED/CRITICAL.
4. Execute relevant runbook (see 6.1–6.3).
5. Log actions in incident tracker (beads / jira).
6. Resolve page when SLA restored or mitigation complete.
```

---

## 7. Baseline Verification & Calibration

### 7.1 Baseline Benchmark Suite

Run these benchmarks monthly to verify SLA baselines remain accurate:

```bash
# 1. Latency baseline (single mission, no load)
python3 scripts/benchmark_latency.py --missions 100 --concurrency 1 --output latency_single.json

# 2. Throughput baseline (max sustained throughput)
python3 scripts/benchmark_throughput.py --duration_sec 300 --output throughput.json

# 3. Capacity stress test (gradual concurrency ramp)
python3 scripts/benchmark_capacity.py --max_concurrency 50 --ramp_rate 2 --output capacity_stress.json

# 4. Token burn baseline (diverse mission types)
python3 scripts/benchmark_token_burn.py --mission_types 10 --output token_burn.json
```

**Acceptance Criteria:**
- p50 latencies within ±10% of baseline.
- p95 latencies within ±15% of baseline.
- p99 latencies within ±20% of baseline.
- Throughput sustained within ±5%.

If regressions exceed thresholds, trigger performance investigation (profiling, tracing).

### 7.2 Quarterly SLA Review

**Cadence:** Last Friday of every quarter.

**Review Checklist:**
- [ ] p95 latency trend (is it creeping up?).
- [ ] Token burn inflation (model cost changes?).
- [ ] Queue depth patterns (retry rate up?).
- [ ] Alert false-positive rate (tuning needed?).
- [ ] Capacity headroom (scaling needed next quarter?).
- [ ] New bottlenecks identified (profiling output).

**Output:** Updated SLA targets + runbook improvements.

---

## 8. Integration with Health Cockpit

### 8.1 Cockpit-to-SLA Mapping

The existing `harness_health_check.py` cockpit is extended to emit performance metrics:

```python
def run_all_with_sla_metrics(service_timeout: float = 0.6) -> dict:
    """Extended health cockpit with SLA latency & throughput checks."""
    checks = [
        check_service(...),
        check_hooks(),
        check_routing_log(),
        check_skill_inventory(),
        check_last_go_artifact(),
        check_active_queue(),
        check_leases(),
        # NEW: SLA metric checks
        check_p95_latency(),     # Compare to 200ms baseline
        check_queue_depth(),     # Compare to 30-mission limit
        check_token_burn(),      # Compare to 2x baseline threshold
    ]
    # ... aggregate to GREEN/YELLOW/RED ...
    return result
```

**New Checks:**
```python
def check_p95_latency(baseline_ms: int = 200, window_min: int = 5) -> Check:
    """Measure p95 latency from mission_audit.jsonl (sliding 5-min window)."""
    # Read last 5 minutes of JSONL, compute p95
    # PASS if p95 <= baseline_ms
    # WARN if baseline_ms < p95 <= 500ms
    # FAIL if p95 > 500ms

def check_queue_depth(red_threshold: int = 30, yellow_threshold: int = 15) -> Check:
    """Measure active mission queue depth."""
    # Count 'pending' + 'executing' missions from mission_store
    # PASS if depth < yellow_threshold
    # WARN if yellow_threshold <= depth < red_threshold
    # FAIL if depth >= red_threshold

def check_token_burn(baseline_tokens_per_min: int = 500_000) -> Check:
    """Measure token burn rate (rolling 1-min window)."""
    # Aggregate token_burn from completed missions in last 1 min
    # PASS if burn <= baseline
    # WARN if baseline < burn <= 2x baseline
    # FAIL if burn > 3x baseline
```

### 8.2 ERROR_LOG Integration

All SLA alerts are written to `07_LOGS_AND_AUDIT/ERROR_LOG` in structured format:

```
[2026-06-20T14:22:45.123Z] ERROR [SLA:LATENCY_BREACH] p99_latency_ms=625 threshold=500 mission_queue_depth=18
[2026-06-20T14:22:50.456Z] WARN  [SLA:TOKEN_BURN_SPIKE] burn_rate=1200000 tokens/min baseline=500000 missions_in_flight=12
[2026-06-20T14:23:00.789Z] ERROR [SLA:RED_TRIGGERED] escalation=PagerDuty runbook=https://...
```

---

## 9. Exception Handling & Graceful Degradation

### 9.1 Bounded vs. Unbounded Missions

**Bounded Mission (predictable latency):**
- Explicit tool list, token budget, scope.
- E2E SLA: <2 seconds.
- Example: "Refactor this function [bounded scope]".

**Unbounded Mission (variable latency):**
- Open agent autonomy, discovery phase.
- E2E SLA: <5 seconds (relaxed, no hard guarantee).
- Example: "Improve test coverage [scope TBD]".

Dashboards and alerts differentiate these modes. Unbounded missions do not count toward strict SLA compliance.

### 9.2 Graceful Degradation Tiers

```
TIER      CONCURRENT | p99 LATENCY | QUEUE | ACTIONS
──────────────────────────────────────────────────────────
GREEN      < 10      | < 300ms     | < 5   | All gates enabled, full audit
YELLOW     10–30     | 300–800ms   | 5–20  | Reduce confidence gate threshold
RED        30–50     | 800–3000ms  | 20–40 | Queue bounded missions only
CRITICAL   > 50      | > 3000ms    | > 40  | Halt intake, drain queue, diagnose
```

When transitioning to YELLOW/RED:
1. Log action to mission_audit.jsonl with `degradation_tier` flag.
2. Adjust confidence gate thresholds (increase from 75→85→90).
3. Prioritize queue (FIFO → token burn awareness).
4. Page on-call if CRITICAL.

---

## 10. Appendix: Key Contacts & Escalation

| Role | Contact | Escalation SLA |
|------|---------|-----------------|
| **On-Call Engineer** | PagerDuty (primary) | 2 min response |
| **Infrastructure Lead** | Slack #infra | 5 min response |
| **Billing/Cost Controller** | Slack #billing | 10 min response |
| **Harness Architect** | GitHub issues | 1 hour |

**Escalation Decision Tree:**
```
LATENCY BREACH (p99 >500ms)
├─ If queue depth high (>20): Scale agents → Infra Lead
├─ If token burn high (>2x baseline): Cost review → Billing
└─ Else: Profiling + investigation → On-Call + Architect

INTEGRITY FAILURE (RED status >5 min)
├─ Page on-call immediately
├─ Notify Infra Lead
└─ Initiate post-incident review within 24h
```

---

## 11. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-20 | Initial SLA baseline, alert rules, cockpit integration, runbooks |

---

## Document Status

- **Last Reviewed:** 2026-06-20
- **Next Review:** 2026-09-20 (quarterly)
- **Owner:** Infrastructure & Observability
- **Stakeholders:** Product, Ops, Billing, Security
- **Approval:** CTO signed off on latency targets & cost constraints
