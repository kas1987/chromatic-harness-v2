"""Tests for magnets.plugins.secrets_plugin — SecretsSurfacePlugin."""

from __future__ import annotations

import sys
from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[3] / "02_RUNTIME"
if str(_RUNTIME) not in sys.path:
    sys.path.insert(0, str(_RUNTIME))

from magnets.base_magnet import MagnetEvent
from magnets.plugin import MagnetPlugin
from magnets.plugins.secrets_plugin import SecretsSurfacePlugin


class TestSecretsSurfacePluginInterface:
    def test_is_magnet_plugin(self):
        assert isinstance(SecretsSurfacePlugin(), MagnetPlugin)

    def test_name(self):
        assert SecretsSurfacePlugin.name == "secrets_surface_plugin"

    def test_observe_returns_magnet_event(self):
        event = SecretsSurfacePlugin().observe("m1", "post_execution", {})
        assert isinstance(event, MagnetEvent)


class TestSecretsSurfacePluginNoHits:
    def test_no_secrets_zero_risk(self):
        event = SecretsSurfacePlugin().observe("m1", "post_execution", {})
        assert event.risk_delta == 0.0

    def test_no_secrets_zero_confidence_delta(self):
        event = SecretsSurfacePlugin().observe("m1", "post_execution", {})
        assert event.confidence_delta == 0.0

    def test_no_secrets_no_evidence(self):
        event = SecretsSurfacePlugin().observe("m1", "post_execution", {})
        assert event.evidence == []

    def test_no_secrets_default_action(self):
        event = SecretsSurfacePlugin().observe("m1", "post_execution", {})
        assert event.recommended_action == "none"

    def test_empty_list_no_hits(self):
        event = SecretsSurfacePlugin().observe(
            "m1", "post_execution", {"secrets_detected": []}
        )
        assert event.risk_delta == 0.0


class TestSecretsSurfacePluginWithHits:
    def test_one_hit_raises_risk(self):
        event = SecretsSurfacePlugin().observe(
            "m1", "post_execution", {"secrets_detected": ["AWS_SECRET_KEY"]}
        )
        assert event.risk_delta > 0

    def test_one_hit_recommends_halt(self):
        event = SecretsSurfacePlugin().observe(
            "m1", "post_execution", {"secrets_detected": ["API_KEY"]}
        )
        assert event.recommended_action == "halt"

    def test_one_hit_negative_confidence(self):
        event = SecretsSurfacePlugin().observe(
            "m1", "post_execution", {"secrets_detected": ["TOKEN"]}
        )
        assert event.confidence_delta == -0.15

    def test_one_hit_evidence_message(self):
        event = SecretsSurfacePlugin().observe(
            "m1", "post_execution", {"secrets_detected": ["TOKEN"]}
        )
        assert any("1 hit(s)" in e for e in event.evidence)

    def test_multiple_hits_scale_risk(self):
        one_event = SecretsSurfacePlugin().observe(
            "m1", "post_execution", {"secrets_detected": ["k1"]}
        )
        three_event = SecretsSurfacePlugin().observe(
            "m1", "post_execution", {"secrets_detected": ["k1", "k2", "k3"]}
        )
        assert three_event.risk_delta > one_event.risk_delta

    def test_many_hits_risk_capped_at_0_4(self):
        hits = [f"key{i}" for i in range(100)]
        event = SecretsSurfacePlugin().observe(
            "m1", "post_execution", {"secrets_detected": hits}
        )
        assert event.risk_delta <= 0.4

    def test_secret_hits_alias(self):
        """secret_hits key should also be recognized."""
        event = SecretsSurfacePlugin().observe(
            "m1", "post_execution", {"secret_hits": ["PASSWORD"]}
        )
        assert event.risk_delta > 0

    def test_hit_count_in_evidence(self):
        hits = ["k1", "k2", "k3"]
        event = SecretsSurfacePlugin().observe(
            "m1", "post_execution", {"secrets_detected": hits}
        )
        assert any("3 hit(s)" in e for e in event.evidence)

    def test_signal_passthrough(self):
        sig = {"secrets_detected": ["TOKEN"], "other_key": "value"}
        event = SecretsSurfacePlugin().observe("m1", "post_execution", sig)
        assert event.observed_signal is sig
