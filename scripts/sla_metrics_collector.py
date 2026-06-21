#!/usr/bin/env python3
"""SLA Metrics Collector — real-time performance observation & alert emission.

Tracks mission latencies, queue depth, token burn, and emits alerts to ERROR_LOG
when SLA thresholds are breached.

Usage:
    python3 sla_metrics_collector.py --config config.json --output metrics.jsonl
    python3 sla_metrics_collector.py --daemon  # Run as background service
    python3 sla_metrics_collector.py --cockpit  # Print current cockpit status
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections import deque

REPO = Path(__file__).resolve().parents[1]
LOGS_DIR = REPO / "07_LOGS_AND_AUDIT"
METRICS_DIR = LOGS_DIR / "metrics"
ERROR_LOG = LOGS_DIR / "ERROR_LOG"
MISSION_AUDIT = LOGS_DIR / "missions"

# Default SLA baselines (from OBSERVABILITY_SLA.md)
DEFAULT_SLA_CONFIG = {
    "latency_p95_baseline_ms": 100,
    "latency_p95_threshold_warn_ms": 200,
    "latency_p95_threshold_page_ms": 500,
    "latency_p99_threshold_sla_ms": 2500,
    "queue_depth_yellow_threshold": 15,
    "queue_depth_red_threshold": 30,
    "token_burn_baseline_per_min": 500_000,
    "token_burn_threshold_warn_multiplier": 2.0,
    "token_burn_threshold_page_multiplier": 3.0,
    "window_size_minutes": 5,
    "snapshot_interval_seconds": 60,
    "escalation_delay_minutes": 5,
}


@dataclass
class LatencySnapshot:
    """Single latency measurement from mission_audit.jsonl."""

    mission_id: str
    phase: str
    latency_ms: int
    timestamp_utc: str


@dataclass
class Metrics:
    """Current operational metrics snapshot."""

    timestamp_utc: str
    window_minutes: int
    p50_latency_ms: int
    p95_latency_ms: int
    p99_latency_ms: int
    mission_count: int
    queue_depth: int
    token_burn_per_min: int
    token_burn_multiplier: float
    cpu_percent: float
    memory_gb: float
    overall_status: str  # green | yellow | red | critical
    readiness_score: int  # 0-100
    alerts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Alert:
    """SLA alert record."""

    timestamp_utc: str
    severity: str  # warn | page | exec
    category: str  # latency | queue | token_burn | integrity
    message: str
    metric_value: Any = None
    threshold_value: Any = None
    mission_id: str | None = None
    runbook_url: str | None = None


class LatencyHistogram:
    """Sliding window latency tracker (ring buffer)."""

    def __init__(self, window_size_minutes: int = 5):
        self.window_minutes = window_size_minutes
        self.max_samples = window_size_minutes * 60  # Assume ~1 sample/sec
        self.samples: deque[int] = deque(maxlen=self.max_samples)

    def add(self, latency_ms: int) -> None:
        self.samples.append(latency_ms)

    def p50(self) -> int:
        if not self.samples:
            return 0
        return sorted(self.samples)[len(self.samples) // 2]

    def p95(self) -> int:
        if not self.samples:
            return 0
        return sorted(self.samples)[int(len(self.samples) * 0.95)]

    def p99(self) -> int:
        if not self.samples:
            return 0
        return sorted(self.samples)[int(len(self.samples) * 0.99)]

    def count(self) -> int:
        return len(self.samples)


class SLAMetricsCollector:
    """Main collector: observes missions, aggregates metrics, emits alerts."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or DEFAULT_SLA_CONFIG
        self.latency_histogram = LatencyHistogram(
            window_size_minutes=self.config.get("window_size_minutes", 5)
        )
        self.alerts_queue: list[Alert] = []
        self.last_page_ts: dict[str, float] = {}  # Track escalation cooldown
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _log_alert(self, alert: Alert) -> None:
        """Write alert to ERROR_LOG and queue."""
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            line = f"[{alert.timestamp_utc}] {alert.severity.upper():6} [SLA:{alert.category.upper()}] {alert.message}"
            f.write(line + "\n")
        self.alerts_queue.append(alert)

    def observe_mission_latency(self, mission_id: str, phase: str, latency_ms: int) -> None:
        """Record a mission phase latency."""
        self.latency_histogram.add(latency_ms)

    def measure_current_metrics(self) -> Metrics:
        """Measure all SLA metrics for current snapshot."""
        p50 = self.latency_histogram.p50()
        p95 = self.latency_histogram.p95()
        p99 = self.latency_histogram.p99()
        mission_count = self.latency_histogram.count()

        # TODO: Wire queue depth and token burn from mission store / beads
        queue_depth = self._measure_queue_depth()
        token_burn = self._measure_token_burn_per_min()
        token_burn_multiplier = token_burn / self.config.get("token_burn_baseline_per_min", 500_000)

        # TODO: Wire CPU/memory from psutil
        cpu_percent = 0.0
        memory_gb = 0.0

        # Compute overall status
        overall_status = self._compute_overall_status(p95, queue_depth, token_burn_multiplier)
        readiness_score = self._compute_readiness_score(p95, queue_depth, token_burn_multiplier)

        metrics = Metrics(
            timestamp_utc=self._utc_now(),
            window_minutes=self.config.get("window_size_minutes", 5),
            p50_latency_ms=int(p50),
            p95_latency_ms=int(p95),
            p99_latency_ms=int(p99),
            mission_count=mission_count,
            queue_depth=queue_depth,
            token_burn_per_min=int(token_burn),
            token_burn_multiplier=round(token_burn_multiplier, 2),
            cpu_percent=cpu_percent,
            memory_gb=memory_gb,
            overall_status=overall_status,
            readiness_score=readiness_score,
        )

        # Check SLA thresholds and emit alerts
        self._check_sla_thresholds(metrics)

        return metrics

    def _measure_queue_depth(self) -> int:
        """Return current mission queue depth (pending + executing)."""
        # TODO: Query mission_store or beads queue
        # For now, stub with 0
        return 0

    def _measure_token_burn_per_min(self) -> int:
        """Return rolling 1-min token burn rate."""
        # TODO: Aggregate token_burn from mission_audit.jsonl last 1 min
        # For now, stub with baseline
        return self.config.get("token_burn_baseline_per_min", 500_000)

    def _compute_overall_status(self, p95_ms: float, queue_depth: int, token_multiplier: float) -> str:
        """Compute traffic-light status."""
        if (
            p95_ms > self.config.get("latency_p95_threshold_page_ms", 500)
            or queue_depth >= self.config.get("queue_depth_red_threshold", 30)
            or token_multiplier > self.config.get("token_burn_threshold_page_multiplier", 3.0)
        ):
            return "red"
        elif (
            p95_ms > self.config.get("latency_p95_threshold_warn_ms", 200)
            or queue_depth >= self.config.get("queue_depth_yellow_threshold", 15)
            or token_multiplier > self.config.get("token_burn_threshold_warn_multiplier", 2.0)
        ):
            return "yellow"
        return "green"

    def _compute_readiness_score(self, p95_ms: float, queue_depth: int, token_multiplier: float) -> int:
        """Compute readiness score (0-100)."""
        score = 100
        # Latency penalty
        if p95_ms > 500:
            score -= 30
        elif p95_ms > 200:
            score -= 15
        # Queue penalty
        if queue_depth >= 30:
            score -= 25
        elif queue_depth >= 15:
            score -= 10
        # Token burn penalty
        if token_multiplier > 3.0:
            score -= 25
        elif token_multiplier > 2.0:
            score -= 10
        return max(0, score)

    def _check_sla_thresholds(self, metrics: Metrics) -> None:
        """Emit alerts if SLA thresholds breached."""
        now_ts = time.time()

        # Latency alerts
        if metrics.p95_latency_ms > self.config.get("latency_p95_threshold_page_ms", 500):
            self._emit_page_with_cooldown(
                key="latency_page",
                delay_minutes=self.config.get("escalation_delay_minutes", 5),
                now_ts=now_ts,
                alert=Alert(
                    timestamp_utc=metrics.timestamp_utc,
                    severity="page",
                    category="latency",
                    message=f"p95 latency {metrics.p95_latency_ms}ms exceeds SLA {self.config.get('latency_p95_threshold_page_ms')}ms",
                    metric_value=metrics.p95_latency_ms,
                    threshold_value=self.config.get("latency_p95_threshold_page_ms"),
                ),
            )
        elif metrics.p95_latency_ms > self.config.get("latency_p95_threshold_warn_ms", 200):
            alert = Alert(
                timestamp_utc=metrics.timestamp_utc,
                severity="warn",
                category="latency",
                message=f"p95 latency {metrics.p95_latency_ms}ms above baseline {self.config.get('latency_p95_baseline_ms')}ms",
                metric_value=metrics.p95_latency_ms,
                threshold_value=self.config.get("latency_p95_threshold_warn_ms"),
            )
            self._log_alert(alert)

        # Queue depth alerts
        if metrics.queue_depth >= self.config.get("queue_depth_red_threshold", 30):
            self._emit_page_with_cooldown(
                key="queue_red",
                delay_minutes=self.config.get("escalation_delay_minutes", 5),
                now_ts=now_ts,
                alert=Alert(
                    timestamp_utc=metrics.timestamp_utc,
                    severity="page",
                    category="queue",
                    message=f"mission queue depth {metrics.queue_depth} >= capacity {self.config.get('queue_depth_red_threshold')}",
                    metric_value=metrics.queue_depth,
                    threshold_value=self.config.get("queue_depth_red_threshold"),
                ),
            )
        elif metrics.queue_depth >= self.config.get("queue_depth_yellow_threshold", 15):
            alert = Alert(
                timestamp_utc=metrics.timestamp_utc,
                severity="warn",
                category="queue",
                message=f"mission queue depth {metrics.queue_depth} rising (yellow threshold {self.config.get('queue_depth_yellow_threshold')})",
                metric_value=metrics.queue_depth,
                threshold_value=self.config.get("queue_depth_yellow_threshold"),
            )
            self._log_alert(alert)

        # Token burn alerts
        if metrics.token_burn_multiplier > self.config.get("token_burn_threshold_page_multiplier", 3.0):
            self._emit_page_with_cooldown(
                key="token_burn_page",
                delay_minutes=self.config.get("escalation_delay_minutes", 5),
                now_ts=now_ts,
                alert=Alert(
                    timestamp_utc=metrics.timestamp_utc,
                    severity="page",
                    category="token_burn",
                    message=f"token burn rate {metrics.token_burn_per_min}/min is {metrics.token_burn_multiplier}x baseline",
                    metric_value=metrics.token_burn_per_min,
                    threshold_value=int(
                        self.config.get("token_burn_baseline_per_min", 500_000)
                        * self.config.get("token_burn_threshold_page_multiplier", 3.0)
                    ),
                ),
            )
        elif metrics.token_burn_multiplier > self.config.get("token_burn_threshold_warn_multiplier", 2.0):
            alert = Alert(
                timestamp_utc=metrics.timestamp_utc,
                severity="warn",
                category="token_burn",
                message=f"token burn rate {metrics.token_burn_per_min}/min is {metrics.token_burn_multiplier}x baseline",
                metric_value=metrics.token_burn_per_min,
                threshold_value=int(
                    self.config.get("token_burn_baseline_per_min", 500_000)
                    * self.config.get("token_burn_threshold_warn_multiplier", 2.0)
                ),
            )
            self._log_alert(alert)

    def _emit_page_with_cooldown(
        self, key: str, delay_minutes: int, now_ts: float, alert: Alert
    ) -> None:
        """Emit a PAGE alert only if cooldown expired."""
        last_page = self.last_page_ts.get(key, 0)
        cooldown_sec = delay_minutes * 60
        if now_ts - last_page > cooldown_sec:
            self._log_alert(alert)
            self.last_page_ts[key] = now_ts

    def export_metrics(self, output_path: Path) -> None:
        """Export current metrics snapshot to JSONL."""
        metrics = self.measure_current_metrics()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(metrics), default=str) + "\n")

    def export_cockpit(self) -> dict[str, Any]:
        """Return structured cockpit status for dashboards."""
        metrics = self.measure_current_metrics()
        return {
            "timestamp_utc": metrics.timestamp_utc,
            "overall_status": metrics.overall_status,
            "readiness_score": metrics.readiness_score,
            "performance": {
                "p50_latency_ms": metrics.p50_latency_ms,
                "p95_latency_ms": metrics.p95_latency_ms,
                "p99_latency_ms": metrics.p99_latency_ms,
                "mission_count": metrics.mission_count,
            },
            "capacity": {
                "queue_depth": metrics.queue_depth,
                "queue_depth_yellow_threshold": self.config.get("queue_depth_yellow_threshold"),
                "queue_depth_red_threshold": self.config.get("queue_depth_red_threshold"),
                "token_burn_per_min": metrics.token_burn_per_min,
                "token_burn_multiplier": metrics.token_burn_multiplier,
            },
            "alerts": [asdict(a) for a in self.alerts_queue[-10:]],  # Last 10 alerts
        }


def main() -> int:
    ap = argparse.ArgumentParser(description="SLA Metrics Collector (production telemetry)")
    ap.add_argument("--config", type=str, help="JSON config file (optional)")
    ap.add_argument("--output", type=str, help="Output metrics JSONL path")
    ap.add_argument("--cockpit", action="store_true", help="Print current cockpit status and exit")
    ap.add_argument("--daemon", action="store_true", help="Run continuously, emitting snapshots every 60s")
    args = ap.parse_args()

    # Load config
    config = DEFAULT_SLA_CONFIG.copy()
    if args.config and Path(args.config).is_file():
        config.update(json.loads(Path(args.config).read_text(encoding="utf-8")))

    collector = SLAMetricsCollector(config)

    # Cockpit mode: print status once and exit
    if args.cockpit:
        cockpit = collector.export_cockpit()
        print(json.dumps(cockpit, indent=2, default=str))
        return 0

    # Export mode: measure once and write to file
    if args.output:
        output_path = Path(args.output)
        collector.export_metrics(output_path)
        print(f"Metrics written to {output_path}")
        return 0

    # Daemon mode: run continuously
    if args.daemon:
        print("SLA Metrics Collector running in daemon mode (Ctrl+C to stop)...")
        try:
            while True:
                metrics = collector.measure_current_metrics()
                # TODO: Emit to time-series DB or central logging system
                time.sleep(collector.config.get("snapshot_interval_seconds", 60))
        except KeyboardInterrupt:
            print("\nCollector stopped.")
            return 0

    # Default: measure once and print
    metrics = collector.measure_current_metrics()
    print(json.dumps(asdict(metrics), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
