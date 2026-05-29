"""Integration tests for Agent Lead synthesis API endpoint."""

import os
import tempfile
import importlib
import pytest

_tmpdir = tempfile.mkdtemp()
os.environ.setdefault("CHROMATIC_DB_PATH", os.path.join(_tmpdir, "synth_test.sqlite"))

import api.db as db_module  # noqa: E402
import api.main as api_module  # noqa: E402

importlib.reload(db_module)
importlib.reload(api_module)

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(api_module.app) as c:
        yield c


class TestSynthesizeEndpoint:
    def test_synthesize_mission_with_events(self, client):
        r = client.post("/missions", json={"objective": "synthesis test mission"})
        assert r.status_code == 200
        mission_id = r.json()["mission_id"]

        client.post(
            f"/missions/{mission_id}/events",
            json={
                "magnet_name": "confidence_magnet",
                "inflection_point": "validation",
                "observed_signal": {"pass": True},
                "risk_delta": -0.05,
                "confidence_delta": 10.0,
                "recommended_action": "proceed",
            },
        )

        r = client.post(f"/missions/{mission_id}/synthesize")
        assert r.status_code == 200
        body = r.json()
        assert body["mission_id"] == mission_id
        assert body["decision"]
        assert body["final_report"]["executive_summary"]
        assert body["handoff_prep"]["directive_summary"]

    def test_synthesize_unknown_mission_404(self, client):
        r = client.post("/missions/CHR-NOPE/synthesize")
        assert r.status_code == 404

    def test_synthesize_creates_bead_on_halt(self, client):
        r = client.post("/missions", json={"objective": "risky deploy"})
        mission_id = r.json()["mission_id"]
        client.post(
            f"/missions/{mission_id}/events",
            json={
                "magnet_name": "security_magnet",
                "inflection_point": "execution",
                "observed_signal": {"leak": True},
                "risk_delta": 0.8,
                "confidence_delta": -40.0,
                "recommended_action": "halt_and_revert",
                "evidence": ["secret"],
            },
        )
        r = client.post(f"/missions/{mission_id}/synthesize?create_bead=true")
        assert r.status_code == 200
        body = r.json()
        if body["decision"] == "halt":
            assert body["bead_created"] is not None
            assert body["bead_created"]["source"] == "agent_lead"
