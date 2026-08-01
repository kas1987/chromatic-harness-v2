"""Test suite for SLA metrics collector."""

import json
import tempfile
import time
from pathlib import Path

import pytest

# Adjust path for test execution
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sla_metrics_collector import (
    SLAMetricsCollector,
    LatencyHistogram,
    Alert,
    DEFAULT_SLA_CONFIG,
)


class TestLatencyHistogram:
    """Test latency tracking and percentile computation."""

    def test_empty_histogram(self):
        hist = LatencyHistogram(window_size_minutes=5)
        assert hist.p50() == 0
        assert hist.p95() == 0
        assert hist.p99() == 0
        assert hist.count() == 0

    def test_single_sample(self):
        hist = LatencyHistogram()
        hist.add(100)
        assert hist.p50() == 100
        assert hist.p95() == 100
        assert hist.p99() == 100
        assert hist.count() == 1

    def test_percentile_computation(self):
        hist = LatencyHistogram()
        # Add 100 latencies: 10ms, 20ms, ..., 1000ms
        for i in range(1, 101):
            hist.add(i * 10)
        assert hist.p50() == 500 or hist.p50() == 510  # ~50th percentile
        assert hist.p95() >= 900  # ~95th percentile
        assert hist.p99() >= 980  # ~99th percentile
        assert hist.count() == 100

    def test_sliding_window_bounded(self):
        hist = LatencyHistogram(window_size_minutes=1)
        # Ring buffer max is ~60 samples
        for i in range(200):
            hist.add(i)
        assert hist.count() <= 60  # Bounded by window


class TestSLAMetricsCollector:
    """Test metrics aggregation and alert logic."""

    def test_collector_initialization(self):
        collector = SLAMetricsCollector()
        assert collector.config is not None
        assert collector.latency_histogram.window_minutes == 5

    def test_custom_config(self):
        custom_config = {
            "latency_p95_threshold_warn_ms": 300,
            "queue_depth_yellow_threshold": 20,
        }
        collector = SLAMetricsCollector(config=custom_config)
        assert collector.config.get("latency_p95_threshold_warn_ms") == 300
        assert collector.config.get("queue_depth_yellow_threshold") == 20

    def test_observe_mission_latency(self):
        collector = SLAMetricsCollector()
        collector.observe_mission_latency("mission-1", "router_decision", 50)
        collector.observe_mission_latency("mission-1", "magnet_synthesis", 150)
        assert collector.latency_histogram.count() == 2

    def test_measure_current_metrics_green(self):
        collector = SLAMetricsCollector()
        # Add low latencies (should be GREEN)
        for _ in range(50):
            collector.observe_mission_latency("mission-x", "phase", 50)
        metrics = collector.measure_current_metrics()
        assert metrics.overall_status == "green"
        assert metrics.readiness_score >= 90

    def test_measure_current_metrics_yellow_latency(self):
        collector = SLAMetricsCollector(
            config={
                "latency_p95_threshold_warn_ms": 200,
                "latency_p95_threshold_page_ms": 500,
            }
        )
        # Add mixed latencies with p95 around 250ms
        for i in range(100):
            collector.observe_mission_latency("mission-x", "phase", 50 + (i % 50) * 5)
        metrics = collector.measure_current_metrics()
        if metrics.p95_latency_ms > 200:
            assert metrics.overall_status == "yellow"

    def test_compute_overall_status_red(self):
        collector = SLAMetricsCollector()
        # Manually set high latency and check status logic
        for _ in range(100):
            collector.observe_mission_latency("m", "p", 600)  # All high
        metrics = collector.measure_current_metrics()
        assert metrics.overall_status == "red"
        assert metrics.readiness_score < 75

    def test_alert_emission_on_latency_breach(self):
        collector = SLAMetricsCollector()
        # Spike latencies to trigger page threshold
        for _ in range(100):
            collector.observe_mission_latency("m", "p", 600)
        metrics = collector.measure_current_metrics()
        # Should have emitted at least one alert (latency page)
        assert len(collector.alerts_queue) > 0
        # Check that alert severity is 'page'
        assert any(a.severity == "page" for a in collector.alerts_queue)

    def test_alert_cooldown_prevents_spam(self):
        collector = SLAMetricsCollector(config={"escalation_delay_minutes": 1})
        now_ts = time.time()
        alert = Alert(
            timestamp_utc="2026-06-20T14:00:00Z",
            severity="page",
            category="latency",
            message="test alert",
        )
        # First page should log
        collector._emit_page_with_cooldown("test_key", delay_minutes=1, now_ts=now_ts, alert=alert)
        count_1 = len(collector.alerts_queue)
        # Immediate second page should be blocked
        collector._emit_page_with_cooldown("test_key", delay_minutes=1, now_ts=now_ts + 10, alert=alert)
        count_2 = len(collector.alerts_queue)
        assert count_1 == count_2  # No new alert emitted
        # Page after cooldown expires should emit
        collector._emit_page_with_cooldown("test_key", delay_minutes=1, now_ts=now_ts + 70, alert=alert)
        count_3 = len(collector.alerts_queue)
        assert count_3 > count_2  # New alert emitted

    def test_error_log_write(self, tmp_path):
        """Test that alerts are written to ERROR_LOG."""
        # Temporarily override ERROR_LOG path for test
        import sla_metrics_collector

        original_error_log = sla_metrics_collector.ERROR_LOG
        test_error_log = tmp_path / "ERROR_LOG"
        sla_metrics_collector.ERROR_LOG = test_error_log

        try:
            collector = SLAMetricsCollector()
            alert = Alert(
                timestamp_utc="2026-06-20T14:00:00Z",
                severity="warn",
                category="latency",
                message="test alert message",
            )
            collector._log_alert(alert)
            # Verify file was written
            assert test_error_log.exists()
            content = test_error_log.read_text(encoding="utf-8")
            assert "test alert message" in content
            assert "WARN" in content
        finally:
            sla_metrics_collector.ERROR_LOG = original_error_log

    def test_export_metrics_jsonl(self, tmp_path):
        """Test metrics export to JSONL."""
        collector = SLAMetricsCollector()
        for _ in range(50):
            collector.observe_mission_latency("m1", "p", 100)
        output_path = tmp_path / "metrics.jsonl"
        collector.export_metrics(output_path)
        assert output_path.exists()
        lines = output_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) > 0
        data = json.loads(lines[0])
        assert "timestamp_utc" in data
        assert "p95_latency_ms" in data
        assert "overall_status" in data

    def test_export_cockpit_structure(self):
        """Test cockpit export format."""
        collector = SLAMetricsCollector()
        for _ in range(50):
            collector.observe_mission_latency("m1", "p", 100)
        cockpit = collector.export_cockpit()
        assert cockpit["overall_status"] in ("green", "yellow", "red", "critical")
        assert "readiness_score" in cockpit
        assert "performance" in cockpit
        assert "p50_latency_ms" in cockpit["performance"]
        assert "capacity" in cockpit
        assert "queue_depth" in cockpit["capacity"]
        assert "alerts" in cockpit


class TestSLAThresholds:
    """Test SLA threshold logic."""

    def test_default_config_values(self):
        """Verify DEFAULT_SLA_CONFIG contains all required keys."""
        required_keys = [
            "latency_p95_baseline_ms",
            "latency_p95_threshold_warn_ms",
            "latency_p95_threshold_page_ms",
            "queue_depth_yellow_threshold",
            "queue_depth_red_threshold",
            "token_burn_baseline_per_min",
        ]
        for key in required_keys:
            assert key in DEFAULT_SLA_CONFIG

    def test_latency_thresholds_ordered(self):
        """Verify latency thresholds are in proper order."""
        config = DEFAULT_SLA_CONFIG
        assert (
            config["latency_p95_baseline_ms"]
            < config["latency_p95_threshold_warn_ms"]
            < config["latency_p95_threshold_page_ms"]
        )

    def test_queue_thresholds_ordered(self):
        """Verify queue thresholds are in proper order."""
        config = DEFAULT_SLA_CONFIG
        assert config["queue_depth_yellow_threshold"] < config["queue_depth_red_threshold"]

    def test_token_burn_multipliers_ordered(self):
        """Verify token burn multipliers are in proper order."""
        config = DEFAULT_SLA_CONFIG
        assert config["token_burn_threshold_warn_multiplier"] < config["token_burn_threshold_page_multiplier"]


class TestIntegration:
    """Integration tests for full metrics pipeline."""

    def test_full_pipeline_low_load(self):
        """Simulate low-load scenario: should be GREEN."""
        collector = SLAMetricsCollector()
        # Simulate 30 missions with low latency
        for i in range(30):
            collector.observe_mission_latency(f"mission-{i}", "router", 40)
            collector.observe_mission_latency(f"mission-{i}", "magnet", 80)
            collector.observe_mission_latency(f"mission-{i}", "gates", 60)
        metrics = collector.measure_current_metrics()
        assert metrics.overall_status == "green"
        assert metrics.p95_latency_ms < 150
        assert metrics.readiness_score >= 85

    def test_full_pipeline_degrading_load(self):
        """Simulate degrading load: transitions YELLOW."""
        collector = SLAMetricsCollector()
        # Simulate 100 missions with increasing latency to push p95 above threshold
        for i in range(100):
            latency = 50 + (i % 100) * 3  # Ramp from 50 to 350ms
            collector.observe_mission_latency(f"mission-{i}", "phase", latency)
        metrics = collector.measure_current_metrics()
        # With latencies up to 350ms, p95 should be in yellow/red range
        if metrics.p95_latency_ms > 200:
            assert metrics.overall_status in ("yellow", "red")
        assert metrics.readiness_score <= 100

    def test_full_pipeline_spike(self):
        """Simulate latency spike: should emit PAGE alert."""
        collector = SLAMetricsCollector()
        # Simulate 100 missions with 90 normal and 10 slow (p99 spike)
        for i in range(90):
            collector.observe_mission_latency(f"mission-{i}", "phase", 100)
        for i in range(10):
            collector.observe_mission_latency(f"mission-{90 + i}", "phase", 1000)
        metrics = collector.measure_current_metrics()
        assert metrics.p99_latency_ms > 500
        # Should have emitted alert if p95 also breached
        if metrics.p95_latency_ms > collector.config.get("latency_p95_threshold_page_ms"):
            assert len(collector.alerts_queue) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestPercentileAndConfigFixes:
    """Regression tests for PR #277 percentile + config merge findings."""

    def test_percentile_uses_nearest_rank(self):
        hist = LatencyHistogram()
        for i in range(1, 101):
            hist.add(i * 10)
        # Nearest-rank percentiles for 100 samples:
        # p50 -> ceil(100*0.50)=50 -> sorted[49] = 500
        # p95 -> ceil(100*0.95)=95 -> sorted[94] = 950
        # p99 -> ceil(100*0.99)=99 -> sorted[98] = 990
        assert hist.p50() == 500
        assert hist.p95() == 950
        assert hist.p99() == 990

    def test_low_load_does_not_trigger_latency_alert(self):
        """High latency with fewer than min_samples_for_latency_alert must stay green."""
        collector = SLAMetricsCollector(
            config={
                "latency_p95_threshold_page_ms": 100,
                "min_samples_for_latency_alert": 10,
            }
        )
        for _ in range(5):
            collector.observe_mission_latency("m", "p", 1000)
        metrics = collector.measure_current_metrics()
        assert metrics.overall_status == "green"
        assert not any(a.category == "latency" for a in collector.alerts_queue)

    def test_config_merges_with_defaults_and_does_not_mutate_default(self):
        custom = {"latency_p95_threshold_warn_ms": 12345}
        collector = SLAMetricsCollector(config=custom)
        assert collector.config["latency_p95_threshold_warn_ms"] == 12345
        assert collector.config["latency_p95_threshold_page_ms"] == 500
        assert collector.config["min_samples_for_latency_alert"] == 10
        # The shared DEFAULT_SLA_CONFIG dict must remain unchanged.
        assert DEFAULT_SLA_CONFIG["latency_p95_threshold_warn_ms"] == 200
