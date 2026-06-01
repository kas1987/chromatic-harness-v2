"""Deterministic smoke test: proves the core Chromatic Harness v2 loop end-to-end."""

import os
import tempfile
import importlib
import pytest

# Use an isolated temp SQLite — must be set before importing api modules.
_tmpdir = tempfile.mkdtemp()
os.environ["CHROMATIC_DB_PATH"] = os.path.join(_tmpdir, "spine_test.sqlite")

import api.db as db_module  # noqa: E402
import api.main as api_module  # noqa: E402

importlib.reload(db_module)
importlib.reload(api_module)

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Module-scoped client that enters lifespan (runs init_db) once."""
    with TestClient(api_module.app) as c:
        yield c


def test_runtime_spine(client):
    """
    Full end-to-end smoke test for the Chromatic Harness v2 core loop:

    1. POST /missions        → creates a mission, returns mission_id
    2. POST /missions/{id}/events → attaches a magnet event
    3. POST /beads           → creates a bead referencing the mission
    4. GET  /missions        → mission appears in the list
    5. GET  /missions/{id}/events → event is attached and retrievable
    6. GET  /beads           → bead is retrievable
    """

    # ── Step 1: Create a mission ──────────────────────────────────────────────
    r = client.post(
        "/missions",
        json={"objective": "spine-test mission", "required_outputs": ["summary"]},
    )
    assert r.status_code == 200, f"POST /missions failed: {r.text}"
    mission_data = r.json()
    assert "mission_id" in mission_data, "Response must contain mission_id"
    mission_id = mission_data["mission_id"]

    # ── Step 2: Attach a magnet event ─────────────────────────────────────────
    r = client.post(
        f"/missions/{mission_id}/events",
        json={
            "magnet_name": "intent_magnet",
            "inflection_point": "task_start",
            "observed_signal": {"clarity": 0.9},
        },
    )
    assert r.status_code == 200, f"POST /missions/{{id}}/events failed: {r.text}"
    event_data = r.json()
    assert "event_id" in event_data, "Event response must contain event_id"
    event_id = event_data["event_id"]

    # ── Step 3: Create a bead referencing the mission ─────────────────────────
    r = client.post(
        "/beads",
        json={
            "title": "spine-test bead",
            "objective": "verify harness loop is operational",
            "source": "spine-test",
            "mission_id": mission_id,
        },
    )
    assert r.status_code == 200, f"POST /beads failed: {r.text}"
    bead_data = r.json()
    assert "bead_id" in bead_data, "Bead response must contain bead_id"
    bead_id = bead_data["bead_id"]

    # ── Step 4: GET /missions → mission appears in list ───────────────────────
    r = client.get("/missions")
    assert r.status_code == 200, f"GET /missions failed: {r.text}"
    missions = r.json()
    mission_ids = [m["mission_id"] for m in missions]
    assert mission_id in mission_ids, f"Created mission {mission_id} not found in GET /missions"

    # ── Step 5: GET /missions/{id}/events → event retrievable ─────────────────
    r = client.get(f"/missions/{mission_id}/events")
    assert r.status_code == 200, f"GET /missions/{{id}}/events failed: {r.text}"
    events = r.json()
    event_ids = [e["event_id"] for e in events]
    assert event_id in event_ids, f"Created event {event_id} not found in GET /missions/{{id}}/events"

    # ── Step 6: GET /beads → bead retrievable ────────────────────────────────
    r = client.get("/beads")
    assert r.status_code == 200, f"GET /beads failed: {r.text}"
    beads = r.json()
    bead_ids = [b["bead_id"] for b in beads]
    assert bead_id in bead_ids, f"Created bead {bead_id} not found in GET /beads"
