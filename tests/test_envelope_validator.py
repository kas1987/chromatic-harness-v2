"""Tests for the discriminated envelope validator (w0wk.2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "02_RUNTIME"))

from intake.envelope_validator import VALID_KINDS, validate, validate_envelope, validate_payload


# ── Minimal valid payloads for each kind ──────────────────────────────────────

_HARNESS_EVENT = {
    "event_id": "evt-001",
    "timestamp": "2026-06-02T12:00:00Z",
    "task_id": "task-1",
    "agent": "agent_lead",
    "model": "claude-sonnet-4-6",
    "event_type": "execute",
    "confidence_score": 85.0,
    "risk_level": "low",
    "result": "passed",
}

_MAGNET_EVENT = {
    "event_id": "mag-001",
    "mission_id": "m-001",
    "magnet_name": "execution_magnet",
    "inflection_point": "start",
    "timestamp": "2026-06-02T12:00:00Z",
    "observed_signal": {"status": "ok"},
}

_BEAD = {
    "bead_id": "chromatic-harness-v2-abc1",
    "title": "Test bead",
    "priority": "p1",
    "status": "created",
    "objective": "Do a thing",
    "definition_of_done": ["thing is done"],
}


# ── validate_envelope ─────────────────────────────────────────────────────────


class TestValidateEnvelope:
    def test_valid_harness_event(self):
        kind, payload = validate_envelope({"kind": "harness_event", "payload": _HARNESS_EVENT})
        assert kind == "harness_event"
        assert payload == _HARNESS_EVENT

    def test_valid_magnet_event(self):
        kind, _ = validate_envelope({"kind": "magnet_event", "payload": _MAGNET_EVENT})
        assert kind == "magnet_event"

    def test_valid_bead(self):
        kind, _ = validate_envelope({"kind": "bead", "payload": _BEAD})
        assert kind == "bead"

    def test_missing_kind(self):
        with pytest.raises(ValueError, match="Unknown kind"):
            validate_envelope({"payload": _HARNESS_EVENT})

    def test_missing_payload(self):
        with pytest.raises(ValueError, match="payload.*must be a JSON object"):
            validate_envelope({"kind": "harness_event"})

    def test_unknown_kind(self):
        with pytest.raises(ValueError, match="Unknown kind"):
            validate_envelope({"kind": "unknown_type", "payload": {}})

    def test_non_object_payload(self):
        with pytest.raises(ValueError, match="payload.*must be a JSON object"):
            validate_envelope({"kind": "harness_event", "payload": "not-an-object"})

    def test_extra_envelope_fields(self):
        with pytest.raises(ValueError, match="Unexpected envelope fields"):
            validate_envelope({"kind": "bead", "payload": _BEAD, "extra": "field"})

    def test_non_dict_input(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            validate_envelope(["not", "a", "dict"])

    def test_valid_kinds_constant(self):
        assert VALID_KINDS == {"harness_event", "magnet_event", "bead"}


# ── validate_payload ──────────────────────────────────────────────────────────


class TestValidatePayload:
    def test_harness_event_valid(self):
        validate_payload("harness_event", _HARNESS_EVENT)  # no exception

    def test_magnet_event_valid(self):
        validate_payload("magnet_event", _MAGNET_EVENT)  # no exception

    def test_bead_valid(self):
        validate_payload("bead", _BEAD)  # no exception

    def test_harness_event_missing_required(self):
        bad = {k: v for k, v in _HARNESS_EVENT.items() if k != "event_type"}
        with pytest.raises(ValueError, match="event_type"):
            validate_payload("harness_event", bad)

    def test_harness_event_bad_enum(self):
        bad = {**_HARNESS_EVENT, "event_type": "not_valid"}
        with pytest.raises(ValueError, match="not_valid"):
            validate_payload("harness_event", bad)

    def test_magnet_event_missing_mission_id(self):
        bad = {k: v for k, v in _MAGNET_EVENT.items() if k != "mission_id"}
        with pytest.raises(ValueError, match="mission_id"):
            validate_payload("magnet_event", bad)

    def test_bead_missing_bead_id(self):
        bad = {k: v for k, v in _BEAD.items() if k != "bead_id"}
        with pytest.raises(ValueError, match="bead_id"):
            validate_payload("bead", bad)


# ── validate (full round-trip) ────────────────────────────────────────────────


class TestValidate:
    def test_harness_event_round_trip(self):
        envelope = {"kind": "harness_event", "payload": _HARNESS_EVENT}
        kind, payload = validate(envelope)
        assert kind == "harness_event"
        assert payload["event_id"] == "evt-001"

    def test_magnet_event_round_trip(self):
        kind, payload = validate({"kind": "magnet_event", "payload": _MAGNET_EVENT})
        assert kind == "magnet_event"
        assert payload["mission_id"] == "m-001"

    def test_bead_round_trip(self):
        kind, payload = validate({"kind": "bead", "payload": _BEAD})
        assert kind == "bead"
        assert payload["bead_id"] == "chromatic-harness-v2-abc1"

    def test_invalid_envelope_raises(self):
        with pytest.raises(ValueError, match="Unknown kind"):
            validate({"kind": "bogus", "payload": {}})

    def test_invalid_payload_raises(self):
        with pytest.raises(ValueError, match="Payload schema violation"):
            validate({"kind": "harness_event", "payload": {"bad": "data"}})
