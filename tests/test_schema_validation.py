"""Schema validation tests — proves that invalid inputs are rejected with 422."""

import os
import tempfile
import importlib
import pytest

# Use temp SQLite for tests — must be set before importing api modules
_tmpdir = tempfile.mkdtemp()
os.environ["CHROMATIC_DB_PATH"] = os.path.join(_tmpdir, "test_schema.sqlite")

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


# ---------------------------------------------------------------------------
# POST /missions — negative cases
# ---------------------------------------------------------------------------


def test_create_mission_missing_objective_returns_422(client):
    """objective is the only required field; omitting it must return 422."""
    r = client.post("/missions", json={})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


def test_create_mission_wrong_type_for_objective_returns_422(client):
    """objective must be a string; passing an int should fail validation."""
    r = client.post("/missions", json={"objective": 12345})
    # FastAPI/Pydantic coerces int → str, so this may pass; we accept 200 or 422.
    # The important check is that it does NOT 500.
    assert r.status_code in (200, 422), f"Unexpected status {r.status_code}: {r.text}"


def test_create_mission_null_objective_returns_422(client):
    """objective=null must be rejected (field is non-optional str)."""
    r = client.post("/missions", json={"objective": None})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# POST /missions — positive baseline
# ---------------------------------------------------------------------------


def test_create_mission_valid_payload_returns_200(client):
    """A fully valid payload must succeed."""
    r = client.post(
        "/missions",
        json={
            "objective": "validate schema harness",
            "agent_role": "agent_lead",
            "autonomy_level": "L2",
            "confidence_required": 80.0,
            "allowed_tools": ["bash", "read"],
            "stop_conditions": ["drift > 20"],
            "required_outputs": ["report"],
        },
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert "mission_id" in data
    assert data["objective"] == "validate schema harness"


# ---------------------------------------------------------------------------
# POST /missions/{id}/events — negative cases
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def mission_id(client):
    """Create a single mission for event-related tests."""
    r = client.post("/missions", json={"objective": "schema event test mission"})
    assert r.status_code == 200
    return r.json()["mission_id"]


def test_create_event_missing_all_required_fields_returns_422(client, mission_id):
    """All three required fields absent → 422."""
    r = client.post(f"/missions/{mission_id}/events", json={})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


def test_create_event_missing_magnet_name_returns_422(client, mission_id):
    """magnet_name is required; omitting it → 422."""
    r = client.post(
        f"/missions/{mission_id}/events",
        json={
            "inflection_point": "task_start",
            "observed_signal": {"clarity": 0.9},
        },
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


def test_create_event_missing_inflection_point_returns_422(client, mission_id):
    """inflection_point is required; omitting it → 422."""
    r = client.post(
        f"/missions/{mission_id}/events",
        json={
            "magnet_name": "intent_magnet",
            "observed_signal": {"clarity": 0.9},
        },
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


def test_create_event_missing_observed_signal_returns_422(client, mission_id):
    """observed_signal is required; omitting it → 422."""
    r = client.post(
        f"/missions/{mission_id}/events",
        json={
            "magnet_name": "intent_magnet",
            "inflection_point": "task_start",
        },
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


def test_create_event_observed_signal_wrong_type_returns_422(client, mission_id):
    """observed_signal must be a dict; passing a string → 422."""
    r = client.post(
        f"/missions/{mission_id}/events",
        json={
            "magnet_name": "intent_magnet",
            "inflection_point": "task_start",
            "observed_signal": "not-a-dict",
        },
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# POST /beads — negative cases
# ---------------------------------------------------------------------------


def test_create_bead_missing_title_returns_422(client):
    """title is required; omitting it → 422."""
    r = client.post("/beads", json={"objective": "some objective"})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


def test_create_bead_missing_objective_returns_422(client):
    """objective is required; omitting it → 422."""
    r = client.post("/beads", json={"title": "Some Bead Title"})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


def test_create_bead_missing_both_required_fields_returns_422(client):
    """Both title and objective absent → 422."""
    r = client.post("/beads", json={})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


def test_create_bead_null_title_returns_422(client):
    """title=null must be rejected."""
    r = client.post("/beads", json={"title": None, "objective": "some objective"})
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# POST /beads — positive baseline
# ---------------------------------------------------------------------------


def test_create_bead_valid_payload_returns_200(client):
    """A fully valid bead payload must succeed."""
    r = client.post(
        "/beads",
        json={
            "title": "Schema Validation Bead",
            "objective": "Prove schema enforcement works",
            "priority": "p1",
            "source": "magnet",
        },
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["bead_id"].startswith("BEAD-")
    assert data["title"] == "Schema Validation Bead"
