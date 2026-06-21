# Observability SLA — Implementation Guide

**Status:** Production Runbook  
**Last Updated:** 2026-06-20  
**Audience:** DevOps, Infrastructure, On-Call Engineers  

---

## Overview

This guide walks through integrating the Observability SLA (see `docs/ops/OBSERVABILITY_SLA.md`) into the live Chromatic Harness runtime. It covers wiring metrics collection, alert emission, and cockpit dashboards.

---

## Part 1: Instrumentation — Emitting Metrics

### 1.1 Mission Lifecycle Instrumentation

Wire metrics collection at key decision points in `02_RUNTIME/orchestrator/orchestrator.py` and `02_RUNTIME/console-api/mission-store.ts`.

#### Python: Orchestrator Mission Creation

```python
# In orchestrator.py, route_to_provider() method
import time
from sla_metrics_collector import SLAMetricsCollector

collector = SLAMetricsCollector()  # Or inject via DI

def route_to_provider(self, packet: MissionPacket, call_type: str) -> str:
    """Route mission to model provider. Instrument latency."""
    start_ms = time.perf_counter() * 1000
    
    # Existing routing logic
    selected_model = self._lookup_routing_table(call_type)
    
    latency_ms = int(time.perf_counter() * 1000 - start_ms)
    collector.observe_mission_latency(
        mission_id=packet.mission_id,
        phase="router_decision",
        latency_ms=latency_ms,
    )
    return selected_model
```

#### Python: CMP Gate Evaluation

```python
# In cmp_executor.py, run_gates() method
def run_gates(self, packet: MissionPacket) -> bool:
    """Run all three gates. Instrument latency."""
    start_ms = time.perf_counter() * 1000
    
    intent_pass = self.intent_gate.check(packet)
    scope_pass = self.scope_gate.check(packet)
    confidence_pass = self.confidence_gate.check(packet)
    
    latency_ms = int(time.perf_counter() * 1000 - start_ms)
    collector.observe_mission_latency(
        mission_id=packet.mission_id,
        phase="cmp_gates",
        latency_ms=latency_ms,
    )
    
    return intent_pass and scope_pass and confidence_pass
```

#### Python: Magnet Synthesis

```python
# In magnet_orchestrator.py, process() method
def process(self, mission_id: str, events: list[MagnetEvent]) -> MagnetReport:
    """Process magnet events. Instrument latency."""
    start_ms = time.perf_counter() * 1000
    
    collected = self._collect(mission_id, events)
    normalized = self._normalize(collected)
    correlated = self._correlate(normalized)
    score, confidence_score, risk_score = self._score(correlated)
    feedback = self._feedback(normalized, correlated, score)
    recommendation = self._recommend(score, risk_score, feedback)
    
    latency_ms = int(time.perf_counter() * 1000 - start_ms)
    collector.observe_mission_latency(
        mission_id=mission_id,
        phase="magnet_synthesis",
        latency_ms=latency_ms,
    )
    
    return MagnetReport(...)
```

#### TypeScript: Mission Store Lifecycle

```typescript
// In mission-store.ts
class MissionStore {
  createMission(packet: MissionPacket): StoredMission {
    const mission: StoredMission = {
      packet,
      status: 'pending',
      created_at: Date.now(),  // Captures creation time
    };
    this.missions.set(packet.mission_id, mission);
    return mission;
  }

  updateMissionStatus(mission_id: string, status: StoredMission['status']): void {
    const mission = this.missions.get(mission_id);
    if (mission) {
      mission.status = status;
      if (status === 'executing') {
        mission.started_at = Date.now();  // Execution start
      }
      if (status === 'completed') {
        mission.completed_at = Date.now();  // Execution end
        const e2e_latency = mission.completed_at - mission.created_at;
        // Emit E2E latency to metrics collector
        emitMetric('mission_e2e_latency', {
          mission_id,
          latency_ms: e2e_latency,
          status: 'completed',
        });
      }
    }
  }
}
```

### 1.2 Queue & Concurrency Tracking

Wire queue depth tracking in `02_RUNTIME/console-api/mission-store.ts`:

```typescript
class MissionStore {
  getQueueDepth(): number {
    const missions = Array.from(this.missions.values());
    return missions.filter(m => 
      m.status === 'pending' || m.status === 'executing'
    ).length;
  }

  // Called periodically (every 60s) by metrics snapshot
  emitQueueMetric(): void {
    const depth = this.getQueueDepth();
    emitMetric('queue_depth', {
      depth,
      timestamp_utc: new Date().toISOString(),
    });
  }
}
```

### 1.3 Token Burn Tracking

Wire token accounting in agent execution:

```python
# In orchestrator.py, execute_mission() method
def execute_mission(self, packet: MissionPacket) -> ExecutionResult:
    """Execute mission via agent. Track token burn."""
    token_budget = packet.metadata.get('token_budget', 0)
    tokens_used = 0
    
    try:
        result = self.agent.run(packet.objective)  # Async execution
        tokens_used = self.agent.tokens_used()  # After completion
    except Exception as exc:
        tokens_used = self.agent.tokens_used()
        raise
    finally:
        # Always emit token burn
        emitMetric('mission_token_burn', {
            mission_id=packet.mission_id,
            tokens_used=tokens_used,
            token_budget=token_budget,
            overrun=(tokens_used > token_budget),
        })
    return result
```

---

## Part 2: Metrics Aggregation & Alert Rules

### 2.1 Metrics Collection Daemon

Run the `sla_metrics_collector.py` script as a background daemon:

```bash
# In docker-compose.yml or systemd unit
python3 /repo/scripts/sla_metrics_collector.py \
  --config /repo/.config/sla_metrics.json \
  --daemon
```

**Config file** (`~/.config/sla_metrics.json`):
```json
{
  "latency_p95_baseline_ms": 100,
  "latency_p95_threshold_warn_ms": 200,
  "latency_p95_threshold_page_ms": 500,
  "latency_p99_threshold_sla_ms": 2500,
  "queue_depth_yellow_threshold": 15,
  "queue_depth_red_threshold": 30,
  "token_burn_baseline_per_min": 500000,
  "token_burn_threshold_warn_multiplier": 2.0,
  "token_burn_threshold_page_multiplier": 3.0,
  "window_size_minutes": 5,
  "snapshot_interval_seconds": 60,
  "escalation_delay_minutes": 5
}
```

### 2.2 ERROR_LOG Integration

The metrics collector writes all alerts to `07_LOGS_AND_AUDIT/ERROR_LOG`:

```
[2026-06-20T14:22:45.123Z] WARN  [SLA:LATENCY] p95_latency_ms=250 threshold=200
[2026-06-20T14:22:50.456Z] PAGE  [SLA:QUEUE] queue_depth=32 threshold=30
[2026-06-20T14:22:55.789Z] PAGE  [SLA:TOKEN_BURN] burn_rate=1200000 baseline=500000
```

Monitor this file with log aggregation (ELK, Datadog, etc.):

```bash
# Tail errors in real-time
tail -f 07_LOGS_AND_AUDIT/ERROR_LOG | grep "\[PAGE\]"

# Parse and alert on [PAGE] lines
grep "\[PAGE\]" 07_LOGS_AND_AUDIT/ERROR_LOG | \
  jq 'split("] ") | {time: .[0], severity: .[1], message: .[2]}'
```

### 2.3 Cockpit Dashboard Endpoint

Add a health endpoint to `02_RUNTIME/console-api/console-server.ts`:

```typescript
// In console-server.ts
app.get('/health/cockpit', (req, res) => {
  const cockpit = metricsCollector.export_cockpit();
  res.json(cockpit);
});

// Example response:
// {
//   "timestamp_utc": "2026-06-20T14:22:45Z",
//   "overall_status": "green",
//   "readiness_score": 98,
//   "performance": {
//     "p50_latency_ms": 45,
//     "p95_latency_ms": 150,
//     "p99_latency_ms": 380
//   },
//   "capacity": {
//     "queue_depth": 8,
//     "queue_depth_yellow_threshold": 15,
//     "queue_depth_red_threshold": 30
//   },
//   "alerts": [...]
// }
```

---

## Part 3: Alerting & Escalation

### 3.1 PagerDuty Integration (Optional)

To send PAGE alerts to PagerDuty:

```python
# In sla_metrics_collector.py
import requests

def _emit_page_with_escalation(self, alert: Alert) -> None:
    """Emit PAGE alert and escalate to PagerDuty."""
    self._log_alert(alert)
    
    # POST to PagerDuty Events API
    pagerduty_url = "https://events.pagerduty.com/v2/enqueue"
    pagerduty_token = os.environ.get("PAGERDUTY_INTEGRATION_KEY")
    
    payload = {
        "routing_key": pagerduty_token,
        "event_action": "trigger",
        "dedup_key": f"sla:{alert.category}",
        "payload": {
            "summary": alert.message,
            "severity": "critical" if alert.severity == "page" else "warning",
            "source": "chromatic-harness-sla",
            "timestamp": alert.timestamp_utc,
            "custom_details": {
                "metric_value": alert.metric_value,
                "threshold": alert.threshold_value,
                "runbook": alert.runbook_url or "https://github.com/chromatic-systems/chromatic-harness-v2/docs/ops/OBSERVABILITY_SLA.md",
            }
        }
    }
    
    try:
        r = requests.post(pagerduty_url, json=payload, timeout=5)
        r.raise_for_status()
    except Exception as exc:
        # Fallback: log to ERROR_LOG if PagerDuty fails
        with open(ERROR_LOG, "a") as f:
            f.write(f"[{alert.timestamp_utc}] ERROR [PAGERDUTY_FAIL] {exc}\n")
```

### 3.2 Slack Integration (Optional)

To post alerts to a Slack channel:

```python
def _emit_alert_to_slack(self, alert: Alert) -> None:
    """Post PAGE alert to Slack #ops channel."""
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not slack_webhook:
        return
    
    payload = {
        "text": f"*SLA {alert.category.upper()} ALERT*",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{alert.severity.upper()}*: {alert.message}\n"
                            f"Metric: {alert.metric_value} | Threshold: {alert.threshold_value}",
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Cockpit"},
                        "url": "http://localhost:3030/health/cockpit",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View SLA Runbook"},
                        "url": "https://github.com/.../OBSERVABILITY_SLA.md",
                    }
                ]
            }
        ]
    }
    
    try:
        r = requests.post(slack_webhook, json=payload, timeout=5)
        r.raise_for_status()
    except Exception:
        pass  # Silently fail if Slack unavailable
```

---

## Part 4: Operational Dashboards

### 4.1 Grafana Dashboard (Optional)

If using Prometheus to scrape metrics, create a Grafana dashboard:

```json
{
  "dashboard": {
    "title": "Chromatic Harness SLA",
    "panels": [
      {
        "title": "p95 Latency (5-min window)",
        "targets": [
          {
            "expr": "rate(mission_latency_ms_bucket{quantile=\"0.95\"}[5m])"
          }
        ],
        "thresholds": [
          { "value": 200, "color": "yellow" },
          { "value": 500, "color": "red" }
        ]
      },
      {
        "title": "Mission Queue Depth",
        "targets": [
          {
            "expr": "mission_queue_depth"
          }
        ],
        "thresholds": [
          { "value": 15, "color": "yellow" },
          { "value": 30, "color": "red" }
        ]
      },
      {
        "title": "Token Burn Rate (tokens/min)",
        "targets": [
          {
            "expr": "rate(mission_token_burn_total[1m])"
          }
        ],
        "thresholds": [
          { "value": 1000000, "color": "yellow" },
          { "value": 1500000, "color": "red" }
        ]
      }
    ]
  }
}
```

### 4.2 Console Dashboard (React)

Add a real-time health panel to the React frontend (`05_FRONTEND_CONSOLE`):

```typescript
// In components/HealthPanel.tsx
import React, { useEffect, useState } from 'react';

export const HealthPanel: React.FC = () => {
  const [cockpit, setCockpit] = useState(null);

  useEffect(() => {
    const interval = setInterval(async () => {
      const res = await fetch('http://localhost:3030/health/cockpit');
      const data = await res.json();
      setCockpit(data);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!cockpit) return <div>Loading...</div>;

  const statusColor = {
    green: 'bg-green-200',
    yellow: 'bg-yellow-200',
    red: 'bg-red-200',
    critical: 'bg-red-600',
  }[cockpit.overall_status];

  return (
    <div className={`p-4 rounded ${statusColor}`}>
      <h3>System Status: {cockpit.overall_status.toUpperCase()}</h3>
      <p>Readiness Score: {cockpit.readiness_score}/100</p>
      <p>p95 Latency: {cockpit.performance.p95_latency_ms}ms</p>
      <p>Queue Depth: {cockpit.capacity.queue_depth}/{cockpit.capacity.queue_depth_red_threshold}</p>
      {cockpit.alerts.length > 0 && (
        <div className="mt-4">
          <h4>Active Alerts</h4>
          <ul>
            {cockpit.alerts.map((a, i) => (
              <li key={i} className="text-sm">
                [{a.severity}] {a.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
```

---

## Part 5: Testing & Validation

### 5.1 Unit Tests

Run the test suite to validate metrics collection:

```bash
cd /repo
python3 -m pytest tests/test_sla_metrics_collector.py -v
```

Expected output:
```
test_empty_histogram PASSED
test_percentile_computation PASSED
test_collector_initialization PASSED
test_measure_current_metrics_green PASSED
test_alert_emission_on_latency_breach PASSED
test_export_metrics_jsonl PASSED
...
```

### 5.2 Load Testing

Simulate latency spikes to verify alert emission:

```bash
# Spike test: introduce artificial latency
python3 scripts/sla_metrics_collector.py --config test_spike.json

# Where test_spike.json contains high latencies
```

### 5.3 Cockpit Health Check

Verify the health endpoint is accessible:

```bash
curl http://localhost:3030/health/cockpit | jq .

# Expected output:
# {
#   "timestamp_utc": "2026-06-20T14:22:45Z",
#   "overall_status": "green",
#   "readiness_score": 98,
#   ...
# }
```

---

## Part 6: Deployment Checklist

Before going to production:

- [ ] Instrument all mission lifecycle phases (creation, router, gates, magnet, execution, completion).
- [ ] Deploy `sla_metrics_collector.py` as daemon (systemd or container).
- [ ] Wire `/health/cockpit` endpoint in console server.
- [ ] Configure PagerDuty / Slack integration (if using).
- [ ] Verify ERROR_LOG is being written and monitored.
- [ ] Run baseline benchmark suite to calibrate initial thresholds.
- [ ] Set up Grafana dashboard or equivalent visualization.
- [ ] Train on-call team on SLA escalation procedures (see Part 6 of OBSERVABILITY_SLA.md).
- [ ] Create incident response runbook (link from alert messages).
- [ ] Schedule quarterly SLA review (last Friday of each quarter).

---

## Part 7: Troubleshooting

### Cockpit Shows RED but Metrics Seem Fine

**Diagnosis:**
1. Check if integrity checks are failing: `harness_health_check.py --markdown`.
2. Verify routing_log freshness: `ls -la 07_LOGS_AND_AUDIT/routing/routes_*.jsonl`.
3. Check skill inventory: `find . -name "SKILL.md" | wc -l`.

**Resolution:**
- Refresh routing log: `scripts/harness_health_check.py --write`.
- Re-index skills: `scripts/discover_skills.py`.

### Alerts Not Firing

**Diagnosis:**
1. Verify metrics are being collected: `ls -la 07_LOGS_AND_AUDIT/metrics/`.
2. Check ERROR_LOG for write errors: `tail 07_LOGS_AND_AUDIT/ERROR_LOG`.
3. Verify collector daemon is running: `ps aux | grep sla_metrics_collector`.

**Resolution:**
- Restart collector: `systemctl restart chromatic-metrics-collector`.
- Check disk space: `df -h 07_LOGS_AND_AUDIT/`.
- Verify permissions on ERROR_LOG: `ls -la 07_LOGS_AND_AUDIT/ERROR_LOG`.

### False Positives in Latency Alerts

**Diagnosis:**
1. Check if baseline was calibrated correctly: review `baseline_benchmark_suite()` output.
2. Inspect distribution of latencies: `jq '.latency_ms' 07_LOGS_AND_AUDIT/missions/*.jsonl | sort -n`.
3. Look for outliers (tail of distribution): `jq '.latency_ms' ... | sort -rn | head -20`.

**Resolution:**
- Increase p95 threshold if baselines have shifted: update `latency_p95_threshold_page_ms` in config.
- Add percentile context to alerts: "p95 {value}ms (last baseline {historic}ms, drift {drift}%)".
- Review with team in quarterly SLA review.

---

## References

- **SLA Specification:** `docs/ops/OBSERVABILITY_SLA.md`
- **Metrics Collector Source:** `scripts/sla_metrics_collector.py`
- **Test Suite:** `tests/test_sla_metrics_collector.py`
- **Health Cockpit:** `scripts/harness_health_check.py`
