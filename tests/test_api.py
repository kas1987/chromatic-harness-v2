"""Tests for Chromatic Harness v2 API."""

import os
import tempfile
import importlib
import pytest

# Use temp SQLite for tests — must be set before importing api modules
_tmpdir = tempfile.mkdtemp()
os.environ["CHROMATIC_DB_PATH"] = os.path.join(_tmpdir, "test.sqlite")

import api.db as db_module  # noqa: E402
import api.main as api_module  # noqa: E402

importlib.reload(db_module)
importlib.reload(api_module)

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    """Session-scoped client that enters lifespan (runs init_db) once."""
    with TestClient(api_module.app) as c:
        yield c


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_mission_returns_dispatch(client):
    r = client.post("/missions", json={"objective": "test mission", "required_outputs": ["report"]})
    assert r.status_code == 200
    data = r.json()
    assert "mission_id" in data
    assert len(data["magnets"]) > 0


def test_get_mission_after_create(client):
    r = client.post("/missions", json={"objective": "get-test"})
    assert r.status_code == 200
    mid = r.json()["mission_id"]
    r2 = client.get(f"/missions/{mid}")
    assert r2.status_code == 200
    assert r2.json()["mission_id"] == mid


def test_get_mission_not_found(client):
    r = client.get("/missions/nonexistent-id")
    assert r.status_code == 404


def test_create_event_for_mission(client):
    r = client.post("/missions", json={"objective": "event-test"})
    mid = r.json()["mission_id"]
    r2 = client.post(
        f"/missions/{mid}/events",
        json={
            "magnet_name": "intent_magnet",
            "inflection_point": "task_start",
            "observed_signal": {"clarity": 0.8},
        },
    )
    assert r2.status_code == 200
    assert "event_id" in r2.json()


def test_list_events_for_mission(client):
    r = client.post("/missions", json={"objective": "list-events-test"})
    mid = r.json()["mission_id"]
    for i in range(2):
        client.post(
            f"/missions/{mid}/events",
            json={
                "magnet_name": "scope_magnet",
                "inflection_point": f"checkpoint_{i}",
                "observed_signal": {"i": i},
            },
        )
    r2 = client.get(f"/missions/{mid}/events")
    assert r2.status_code == 200
    assert len(r2.json()) == 2


def test_create_bead(client):
    r = client.post(
        "/beads",
        json={"title": "Fix scope drift", "objective": "Reduce scope violations"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "created"
    assert data["bead_id"].startswith("BEAD-")


def test_list_beads(client):
    client.post("/beads", json={"title": "List test bead", "objective": "test"})
    r = client.get("/beads")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_list_missions(client):
    client.post("/missions", json={"objective": "list-missions-test-1"})
    client.post("/missions", json={"objective": "list-missions-test-2"})
    r = client.get("/missions")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    objectives = [m["objective"] for m in data]
    assert "list-missions-test-1" in objectives
    assert "list-missions-test-2" in objectives
