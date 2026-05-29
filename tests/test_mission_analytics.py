"""Integration tests for mission analytics and event range query endpoints."""

import os
import tempfile
import importlib
import pytest

_tmpdir = tempfile.mkdtemp()
os.environ.setdefault(
    "CHROMATIC_DB_PATH", os.path.join(_tmpdir, "analytics_test.sqlite")
)

import api.db as db_module  # noqa: E402
import api.main as api_module  # noqa: E402

importlib.reload(db_module)
importlib.reload(api_module)

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(api_module.app) as c:
        yield c


@pytest.fixture(scope="module")
def mission_with_events(client):
    """Create a mission and populate it with several magnet events."""
    r = client.post("/missions", json={"objective": "analytics test mission"})
    assert r.status_code == 200
    mission_id = r.json()["mission_id"]

    events = [
        {
            "magnet_name": "confidence_magnet",
            "inflection_point": "validation",
            "observed_signal": {"test_pass": True},
            "risk_delta": -0.05,
            "confidence_delta": 5.0,
            "evidence": [],
            "recommended_action": "proceed",
        },
        {
            "magnet_name": "execution_magnet",
            "inflection_point": "execution",
            "observed_signal": {"tool": "bash"},
            "risk_delta": 0.15,
            "confidence_delta": 0.0,
            "evidence": ["suspicious_tool_call"],
            "recommended_action": "warn",
        },
        {
            "magnet_name": "confidence_magnet",
            "inflection_point": "validation",
            "observed_signal": {"coverage": 0.82},
            "risk_delta": -0.1,
            "confidence_delta": 10.0,
            "evidence": [],
            "recommended_action": "proceed",
        },
        {
            "magnet_name": "scope_magnet",
            "inflection_point": "intake",
            "observed_signal": {"files_changed": 3},
            "risk_delta": 0.05,
            "confidence_delta": 2.0,
            "evidence": [],
            "recommended_action": "monitor",
        },
    ]
    for ev in events:
        r = client.post(f"/missions/{mission_id}/events", json=ev)
        assert r.status_code == 200

    return mission_id


class TestAnalyticsEndpoint:
    def test_returns_200_for_mission_with_events(self, client, mission_with_events):
        r = client.get(f"/missions/{mission_with_events}/analytics")
        assert r.status_code == 200

    def test_event_count_matches(self, client, mission_with_events):
        r = client.get(f"/missions/{mission_with_events}/analytics")
        data = r.json()
        assert data["event_count"] == 4

    def test_confidence_trend_length_matches_events(self, client, mission_with_events):
        r = client.get(f"/missions/{mission_with_events}/analytics")
        data = r.json()
        assert len(data["confidence_trend"]) == 4

    def test_risk_trend_length_matches_events(self, client, mission_with_events):
        r = client.get(f"/missions/{mission_with_events}/analytics")
        data = r.json()
        assert len(data["risk_trend"]) == 4

    def test_confidence_trend_is_cumulative(self, client, mission_with_events):
        r = client.get(f"/missions/{mission_with_events}/analytics")
        data = r.json()
        trend = data["confidence_trend"]
        # Each point should be >= previous (values are 5.0, 0.0, 10.0, 2.0 deltas)
        assert trend[-1]["value"] > trend[0]["value"]

    def test_magnet_breakdown_contains_expected_magnets(
        self, client, mission_with_events
    ):
        r = client.get(f"/missions/{mission_with_events}/analytics")
        data = r.json()
        names = {m["magnet_name"] for m in data["magnet_breakdown"]}
        assert "confidence_magnet" in names
        assert "execution_magnet" in names
        assert "scope_magnet" in names

    def test_confidence_magnet_has_count_2(self, client, mission_with_events):
        r = client.get(f"/missions/{mission_with_events}/analytics")
        data = r.json()
        cm = next(
            m
            for m in data["magnet_breakdown"]
            if m["magnet_name"] == "confidence_magnet"
        )
        assert cm["event_count"] == 2

    def test_top_actions_present(self, client, mission_with_events):
        r = client.get(f"/missions/{mission_with_events}/analytics")
        data = r.json()
        assert len(data["top_actions"]) > 0
        assert data["top_actions"][0]["action"] == "proceed"  # highest count

    def test_empty_analytics_for_unknown_mission(self, client):
        r = client.get("/missions/CHR-UNKNOWN/analytics")
        assert r.status_code == 200
        data = r.json()
        assert data["event_count"] == 0
        assert data["confidence_trend"] == []


class TestEventRangeQuery:
    def test_events_without_filters_returns_all(self, client, mission_with_events):
        r = client.get(f"/missions/{mission_with_events}/events")
        assert r.status_code == 200
        assert len(r.json()) == 4

    def test_from_ts_future_returns_empty(self, client, mission_with_events):
        r = client.get(
            f"/missions/{mission_with_events}/events",
            params={"from_ts": "2099-01-01T00:00:00Z"},
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_to_ts_past_returns_empty(self, client, mission_with_events):
        r = client.get(
            f"/missions/{mission_with_events}/events",
            params={"to_ts": "2000-01-01T00:00:00Z"},
        )
        assert r.status_code == 200
        assert r.json() == []
