"""Tests for Chromatic Harness v2 API (auth-aware)."""

import os
import tempfile
import importlib
import pytest

# Use temp SQLite for tests — must be set before importing api modules
_tmpdir = tempfile.mkdtemp()
os.environ["CHROMATIC_DB_PATH"] = os.path.join(_tmpdir, "test.sqlite")
# These endpoint contract tests run with auth enabled so production-like paths are exercised.
os.environ["AUTH_ENABLED"] = "true"

import auth as auth_module  # noqa: E402
import api.db as db_module  # noqa: E402
import api.main as api_module  # noqa: E402

importlib.reload(auth_module)
importlib.reload(db_module)
importlib.reload(api_module)

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    """Session-scoped client that enters lifespan (runs init_db) once."""
    with TestClient(api_module.app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(client):
    """Bearer token for a test admin user."""  # pragma: allowlist secret
    client.post(
        "/auth/register",
        json={"username": "testapi", "password": "pw", "role": "admin"},  # pragma: allowlist secret
    )  # pragma: allowlist secret
    r = client.post("/auth/token", json={"username": "testapi", "password": "pw"})  # pragma: allowlist secret
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]  # pragma: allowlist secret
    return {"Authorization": f"Bearer {token}"}  # pragma: allowlist secret


@pytest.fixture(scope="session")
def executor_headers(client):
    client.post(
        "/auth/register",
        json={"username": "testexec", "password": "pw", "role": "executor"},  # pragma: allowlist secret
    )  # pragma: allowlist secret
    r = client.post("/auth/token", json={"username": "testexec", "password": "pw"})  # pragma: allowlist secret
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]  # pragma: allowlist secret
    return {"Authorization": f"Bearer {token}"}  # pragma: allowlist secret


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_mission_requires_auth(client):
    r = client.post("/missions", json={"objective": "unauthorized"})
    assert r.status_code == 401


def test_create_mission_returns_dispatch(client, auth_headers):
    r = client.post(
        "/missions", json={"objective": "test mission", "required_output": ["report"]}, headers=auth_headers
    )
    assert r.status_code == 200
    data = r.json()
    assert "mission_id" in data
    assert len(data["magnets"]) > 0


def test_get_mission_after_create(client, auth_headers):
    r = client.post("/missions", json={"objective": "get-test"}, headers=auth_headers)
    assert r.status_code == 200
    mid = r.json()["mission_id"]
    r2 = client.get(f"/missions/{mid}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["mission_id"] == mid


def test_get_mission_not_found(client, auth_headers):
    r = client.get("/missions/nonexistent-id", headers=auth_headers)
    assert r.status_code == 404


def test_create_event_for_mission(client, auth_headers):
    r = client.post("/missions", json={"objective": "event-test"}, headers=auth_headers)
    mid = r.json()["mission_id"]
    r2 = client.post(
        f"/missions/{mid}/events",
        json={
            "magnet_name": "intent_magnet",
            "inflection_point": "task_start",
            "observed_signal": {"clarity": 0.8},
        },
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert "event_id" in r2.json()


def test_list_events_for_mission(client, auth_headers):
    r = client.post("/missions", json={"objective": "list-events-test"}, headers=auth_headers)
    mid = r.json()["mission_id"]
    for i in range(2):
        client.post(
            f"/missions/{mid}/events",
            json={
                "magnet_name": "scope_magnet",
                "inflection_point": f"checkpoint_{i}",
                "observed_signal": {"i": i},
            },
            headers=auth_headers,
        )
    r2 = client.get(f"/missions/{mid}/events", headers=auth_headers)
    assert r2.status_code == 200
    assert len(r2.json()) == 2


def test_create_bead(client, auth_headers):
    r = client.post(
        "/beads",
        json={"title": "Fix scope drift", "objective": "Reduce scope violations"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "created"
    assert data["bead_id"].startswith("BEAD-")


def test_list_beads(client, auth_headers):
    client.post("/beads", json={"title": "List test bead", "objective": "test"}, headers=auth_headers)
    r = client.get("/beads", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_list_missions(client, auth_headers):
    client.post("/missions", json={"objective": "list-missions-test-1"}, headers=auth_headers)
    client.post("/missions", json={"objective": "list-missions-test-2"}, headers=auth_headers)
    r = client.get("/missions", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    objectives = [m["objective"] for m in data]
    assert "list-missions-test-1" in objectives
    assert "list-missions-test-2" in objectives


def test_promote_agent_requires_reviewer_role(client, auth_headers, executor_headers):
    create = client.post(
        "/agents",
        json={"agent_id": "agent-promote-test", "description": "promote", "initial_level": 0},
        headers=auth_headers,
    )
    assert create.status_code == 201, create.text

    forbidden = client.post(
        "/agents/agent-promote-test/promote",
        json={"new_level": 1, "reason": "executor should fail"},
        headers=executor_headers,
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        "/agents/agent-promote-test/promote",
        json={"new_level": 1, "reason": "admin may promote"},
        headers=auth_headers,
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["current_level"] == 1
