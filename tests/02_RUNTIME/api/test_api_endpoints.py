"""Integration tests for the FastAPI API layer (02_RUNTIME/api/main.py).

All tests use FastAPI's TestClient with an in-memory SQLite override so they
are hermetic and never touch the production database.

jose / bcrypt are mocked at module level because their C-extension backends are
unavailable in this environment; auth logic itself is unit-tested in the auth
module's own suite.
"""

from __future__ import annotations

import asyncio
import sys
import unittest.mock as mock
from typing import Any, Generator

import pytest

# ---------------------------------------------------------------------------
# Shim broken C-extension deps BEFORE importing anything from 02_RUNTIME/api
# ---------------------------------------------------------------------------
for _mod in [
    "jose",
    "jose.jwt",
    "jose.jws",
    "jose.jwk",
    "jose.backends",
    "jose.backends.cryptography_backend",
    "jose.backends.base",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = mock.MagicMock()
# JWTError must be a real exception class so `except JWTError` works
sys.modules["jose"].JWTError = Exception

# bcrypt mock: hashpw must return bytes-like object with a .decode() → str
# and checkpw must accept two byte strings and return bool.
# We use a simple plain-text scheme: hashed = "plain:<password>"
_bcrypt_mock = mock.MagicMock()


def _hashpw(plain_bytes: bytes, salt: bytes) -> bytes:
    return b"plain:" + plain_bytes


def _checkpw(plain_bytes: bytes, hashed_bytes: bytes) -> bool:
    return hashed_bytes == b"plain:" + plain_bytes


_bcrypt_mock.hashpw = _hashpw
_bcrypt_mock.gensalt = lambda: b"fakesalt"
_bcrypt_mock.checkpw = _checkpw
sys.modules["bcrypt"] = _bcrypt_mock

# jose token mock: create_access_token should return a deterministic string
# so that login tests can verify response structure without real JWT signing.
import base64 as _base64  # noqa: E402

_jose_jwt_mock = mock.MagicMock()


def _jwt_encode(payload: dict, key: str, algorithm: str = "HS256") -> str:
    data = f"{payload.get('sub', '')}:{payload.get('role', '')}".encode()
    return "mock." + _base64.b64encode(data).decode()


def _jwt_decode(token: str, key: str, algorithms: list) -> dict:
    if not token.startswith("mock."):
        raise Exception("Invalid token")
    data = _base64.b64decode(token[5:]).decode()
    sub, role = data.split(":", 1)
    return {"sub": sub, "role": role}


_jose_jwt_mock.encode = _jwt_encode
_jose_jwt_mock.decode = _jwt_decode
sys.modules["jose"].jwt = _jose_jwt_mock
# Also inject under full dotted name so `from jose import jwt` resolves correctly
sys.modules["jose.jwt"] = _jose_jwt_mock

# ---------------------------------------------------------------------------
# Now safe to import from the api package (conftest already put api on path)
# ---------------------------------------------------------------------------
import aiosqlite  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app, get_db  # noqa: E402

# ---------------------------------------------------------------------------
# In-memory DB helper
# ---------------------------------------------------------------------------

_CREATE_TABLES = [
    """CREATE TABLE IF NOT EXISTS missions (
        mission_id TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS magnet_events (
        event_id TEXT PRIMARY KEY,
        mission_id TEXT NOT NULL,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS beads (
        bead_id TEXT PRIMARY KEY,
        mission_id TEXT,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS agent_profiles (
        agent_id TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'executor',
        created_at TEXT NOT NULL
    )""",
]

# Shared per-test connection reference used by the dependency override.
_db_conn: aiosqlite.Connection | None = None


async def _make_db() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    for stmt in _CREATE_TABLES:
        await conn.execute(stmt)
    await conn.commit()
    return conn


async def _override_get_db():  # async generator used as FastAPI dependency
    global _db_conn
    assert _db_conn is not None, "_db_conn not initialised by fixture"
    yield _db_conn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """TestClient backed by a fresh in-memory SQLite DB for each test."""
    global _db_conn
    _db_conn = asyncio.get_event_loop().run_until_complete(_make_db())
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
    asyncio.get_event_loop().run_until_complete(_db_conn.close())
    _db_conn = None


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


# ---------------------------------------------------------------------------
# /auth/status
# ---------------------------------------------------------------------------


class TestAuthStatus:
    def test_auth_disabled_by_default(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AUTH_ENABLED", raising=False)
        resp = client.get("/auth/status")
        assert resp.status_code == 200
        assert resp.json()["auth_enabled"] is False


# ---------------------------------------------------------------------------
# /auth/register
# ---------------------------------------------------------------------------


class TestAuthRegister:
    def _register(
        self,
        client: TestClient,
        username: str = "alice",
        password: str = "secret123",
        role: str = "executor",
    ) -> Any:
        return client.post(
            "/auth/register",
            json={"username": username, "password": password, "role": role},
        )

    def test_register_success_201(self, client: TestClient) -> None:
        resp = self._register(client)
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "alice"
        assert data["role"] == "executor"
        assert "user_id" in data
        assert "created_at" in data

    def test_register_duplicate_returns_409(self, client: TestClient) -> None:
        self._register(client)
        resp = self._register(client)
        assert resp.status_code == 409

    def test_register_missing_password_returns_422(self, client: TestClient) -> None:
        resp = client.post("/auth/register", json={"username": "bob"})
        assert resp.status_code == 422

    def test_register_missing_username_returns_422(self, client: TestClient) -> None:
        resp = client.post("/auth/register", json={"password": "pw"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /auth/token
# ---------------------------------------------------------------------------


class TestAuthToken:
    def _setup_user(self, client: TestClient) -> None:
        client.post(
            "/auth/register",
            json={"username": "alice", "password": "secret123"},
        )

    def test_login_valid_credentials(self, client: TestClient) -> None:
        self._setup_user(client)
        resp = client.post(
            "/auth/token",
            json={"username": "alice", "password": "secret123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user_id" in data

    def test_login_wrong_password_returns_401(self, client: TestClient) -> None:
        self._setup_user(client)
        resp = client.post(
            "/auth/token",
            json={"username": "alice", "password": "wrong"},
        )
        assert resp.status_code == 401

    def test_login_unknown_user_returns_401(self, client: TestClient) -> None:
        resp = client.post(
            "/auth/token",
            json={"username": "nobody", "password": "x"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields_returns_422(self, client: TestClient) -> None:
        resp = client.post("/auth/token", json={"username": "alice"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------


class TestAuthMe:
    def test_auth_me_when_auth_disabled_returns_401(self, client: TestClient) -> None:
        # auth disabled → get_current_user returns None → endpoint raises 401
        resp = client.get("/auth/me")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /missions  (POST + GET list + GET single)
# ---------------------------------------------------------------------------


class TestMissions:
    def _create(self, client: TestClient, objective: str = "Test mission") -> dict:
        resp = client.post("/missions", json={"objective": objective})
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_list_missions_empty(self, client: TestClient) -> None:
        resp = client.get("/missions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_mission_success(self, client: TestClient) -> None:
        data = self._create(client)
        assert data["objective"] == "Test mission"
        assert data["mission_id"].startswith("CHR-")
        assert "status" in data
        assert isinstance(data["magnets"], list)

    def test_create_mission_defaults(self, client: TestClient) -> None:
        data = self._create(client)
        assert data["agent_role"] == "agent_lead"
        assert data["autonomy_level"] == "L1"
        assert data["confidence_required"] == 75.0

    def test_create_mission_custom_fields(self, client: TestClient) -> None:
        resp = client.post(
            "/missions",
            json={
                "objective": "Custom",
                "agent_role": "specialist",
                "autonomy_level": "L3",
                "confidence_required": 90.0,
                "allowed_tools": ["bash", "read"],
                "stop_conditions": ["success"],
                "required_outputs": ["report"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_role"] == "specialist"
        assert data["autonomy_level"] == "L3"
        assert data["confidence_required"] == 90.0
        assert "bash" in data["allowed_tools"]

    def test_create_mission_missing_objective_returns_422(self, client: TestClient) -> None:
        resp = client.post("/missions", json={"agent_role": "lead"})
        assert resp.status_code == 422

    def test_list_missions_returns_all(self, client: TestClient) -> None:
        self._create(client, "M1")
        self._create(client, "M2")
        resp = client.get("/missions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_mission_success(self, client: TestClient) -> None:
        mid = self._create(client)["mission_id"]
        resp = client.get(f"/missions/{mid}")
        assert resp.status_code == 200
        assert resp.json()["mission_id"] == mid

    def test_get_mission_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get("/missions/CHR-NONEXIST")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /missions/{mission_id}/events
# ---------------------------------------------------------------------------


class TestMissionEvents:
    def _setup_mission(self, client: TestClient) -> str:
        return client.post("/missions", json={"objective": "event test"}).json()["mission_id"]

    def _post_event(self, client: TestClient, mid: str, **kwargs: Any) -> dict:
        payload: dict = {
            "magnet_name": "test_magnet",
            "inflection_point": "phase_start",
            "observed_signal": {"key": "value"},
            **kwargs,
        }
        resp = client.post(f"/missions/{mid}/events", json=payload)
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_create_event_success(self, client: TestClient) -> None:
        mid = self._setup_mission(client)
        ev = self._post_event(client, mid)
        assert ev["mission_id"] == mid
        assert ev["magnet_name"] == "test_magnet"
        assert "event_id" in ev
        assert "timestamp" in ev

    def test_create_event_defaults(self, client: TestClient) -> None:
        mid = self._setup_mission(client)
        ev = self._post_event(client, mid)
        assert ev["risk_delta"] == 0.0
        assert ev["confidence_delta"] == 0.0
        assert ev["evidence"] == []
        assert ev["recommended_action"] == "none"

    def test_create_event_with_deltas(self, client: TestClient) -> None:
        mid = self._setup_mission(client)
        ev = self._post_event(client, mid, risk_delta=0.1, confidence_delta=5.0)
        assert ev["risk_delta"] == pytest.approx(0.1)
        assert ev["confidence_delta"] == pytest.approx(5.0)

    def test_create_event_missing_required_returns_422(self, client: TestClient) -> None:
        mid = self._setup_mission(client)
        # missing inflection_point and observed_signal
        resp = client.post(f"/missions/{mid}/events", json={"magnet_name": "x"})
        assert resp.status_code == 422

    def test_list_events_empty(self, client: TestClient) -> None:
        mid = self._setup_mission(client)
        resp = client.get(f"/missions/{mid}/events")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_events_returns_all(self, client: TestClient) -> None:
        mid = self._setup_mission(client)
        self._post_event(client, mid)
        self._post_event(client, mid, magnet_name="second")
        resp = client.get(f"/missions/{mid}/events")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_events_filter_from_ts_accepts_query(self, client: TestClient) -> None:
        mid = self._setup_mission(client)
        self._post_event(client, mid)
        resp = client.get(
            f"/missions/{mid}/events",
            params={"from_ts": "2000-01-01T00:00:00"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_events_filter_to_ts_far_future_returns_results(self, client: TestClient) -> None:
        mid = self._setup_mission(client)
        self._post_event(client, mid)
        resp = client.get(
            f"/missions/{mid}/events",
            params={"to_ts": "2099-01-01T00:00:00"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_events_filter_to_ts_past_returns_empty(self, client: TestClient) -> None:
        mid = self._setup_mission(client)
        self._post_event(client, mid)
        resp = client.get(
            f"/missions/{mid}/events",
            params={"to_ts": "1999-01-01T00:00:00"},
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# /missions/{mission_id}/analytics
# ---------------------------------------------------------------------------


class TestMissionAnalytics:
    def test_analytics_no_events_returns_empty_struct(self, client: TestClient) -> None:
        mid = client.post("/missions", json={"objective": "analytics test"}).json()["mission_id"]
        resp = client.get(f"/missions/{mid}/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_count"] == 0
        assert data["duration_seconds"] == 0.0
        assert data["confidence_trend"] == []
        assert data["risk_trend"] == []
        assert data["magnet_breakdown"] == []
        assert data["top_actions"] == []

    def test_analytics_with_events(self, client: TestClient) -> None:
        mid = client.post("/missions", json={"objective": "analytics test"}).json()["mission_id"]
        for i in range(3):
            client.post(
                f"/missions/{mid}/events",
                json={
                    "magnet_name": "magnet_a",
                    "inflection_point": "phase",
                    "observed_signal": {},
                    "risk_delta": 0.05 * i,
                    "confidence_delta": 2.0,
                    "recommended_action": "proceed",
                },
            )
        resp = client.get(f"/missions/{mid}/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["event_count"] == 3
        assert len(data["confidence_trend"]) == 3
        assert len(data["risk_trend"]) == 3
        assert data["magnet_breakdown"][0]["magnet_name"] == "magnet_a"
        assert data["magnet_breakdown"][0]["event_count"] == 3
        assert data["top_actions"][0]["action"] == "proceed"
        assert data["avg_confidence_delta"] == pytest.approx(2.0)

    def test_analytics_cumulative_trend_values(self, client: TestClient) -> None:
        mid = client.post("/missions", json={"objective": "trend"}).json()["mission_id"]
        client.post(
            f"/missions/{mid}/events",
            json={
                "magnet_name": "m",
                "inflection_point": "p",
                "observed_signal": {},
                "confidence_delta": 10.0,
            },
        )
        client.post(
            f"/missions/{mid}/events",
            json={
                "magnet_name": "m",
                "inflection_point": "p",
                "observed_signal": {},
                "confidence_delta": 5.0,
            },
        )
        data = client.get(f"/missions/{mid}/analytics").json()
        trend_values = [p["value"] for p in data["confidence_trend"]]
        assert trend_values == [pytest.approx(10.0), pytest.approx(15.0)]


# ---------------------------------------------------------------------------
# /beads
# ---------------------------------------------------------------------------


class TestBeads:
    def _create(self, client: TestClient, title: str = "Test Bead") -> dict:
        resp = client.post(
            "/beads",
            json={"title": title, "objective": "Do something useful"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_list_beads_empty(self, client: TestClient) -> None:
        resp = client.get("/beads")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_bead_success(self, client: TestClient) -> None:
        data = self._create(client)
        assert data["title"] == "Test Bead"
        assert data["bead_id"].startswith("BEAD-")
        assert data["status"] == "created"
        assert data["priority"] == "p2"
        assert data["source"] == "magnet"

    def test_create_bead_custom_priority(self, client: TestClient) -> None:
        resp = client.post(
            "/beads",
            json={"title": "Urgent", "objective": "Fix asap", "priority": "p1"},
        )
        assert resp.status_code == 200
        assert resp.json()["priority"] == "p1"

    def test_create_bead_with_mission_id(self, client: TestClient) -> None:
        resp = client.post(
            "/beads",
            json={
                "title": "Linked",
                "objective": "Linked bead",
                "mission_id": "CHR-ABC123",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["mission_id"] == "CHR-ABC123"

    def test_create_bead_null_mission_id(self, client: TestClient) -> None:
        data = self._create(client)
        assert data["mission_id"] is None

    def test_create_bead_missing_objective_returns_422(self, client: TestClient) -> None:
        resp = client.post("/beads", json={"title": "no obj"})
        assert resp.status_code == 422

    def test_create_bead_missing_title_returns_422(self, client: TestClient) -> None:
        resp = client.post("/beads", json={"objective": "no title"})
        assert resp.status_code == 422

    def test_list_beads_returns_all(self, client: TestClient) -> None:
        self._create(client, "B1")
        self._create(client, "B2")
        resp = client.get("/beads")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# /agents  (register + list + get)
# ---------------------------------------------------------------------------


class TestAgents:
    def _register(self, client: TestClient, agent_id: str = "agent-001", level: int = 0) -> dict:
        resp = client.post(
            "/agents",
            json={
                "agent_id": agent_id,
                "description": "Test agent",
                "initial_level": level,
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    def test_list_agents_empty(self, client: TestClient) -> None:
        resp = client.get("/agents")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_register_agent_success(self, client: TestClient) -> None:
        data = self._register(client)
        assert data["agent_id"] == "agent-001"
        assert data["current_level"] == 0
        assert data["total_executions"] == 0
        assert data["successful_executions"] == 0
        assert data["success_rate"] == 0.0
        assert data["promotion_history"] == []

    def test_register_agent_with_initial_level(self, client: TestClient) -> None:
        data = self._register(client, level=2)
        assert data["current_level"] == 2
        assert len(data["promotion_history"]) == 1
        assert data["promotion_history"][0]["level"] == 2

    def test_register_agent_duplicate_returns_409(self, client: TestClient) -> None:
        self._register(client)
        resp = client.post(
            "/agents",
            json={"agent_id": "agent-001", "description": "Duplicate"},
        )
        assert resp.status_code == 409

    def test_register_agent_invalid_level_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/agents",
            json={"agent_id": "bad", "description": "", "initial_level": 10},
        )
        assert resp.status_code == 422

    def test_register_agent_negative_level_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/agents",
            json={"agent_id": "bad2", "description": "", "initial_level": -1},
        )
        assert resp.status_code == 422

    def test_register_agent_missing_id_returns_422(self, client: TestClient) -> None:
        resp = client.post("/agents", json={"description": "no id"})
        assert resp.status_code == 422

    def test_list_agents_after_register(self, client: TestClient) -> None:
        self._register(client, "a1")
        self._register(client, "a2")
        resp = client.get("/agents")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_agent_success(self, client: TestClient) -> None:
        self._register(client)
        resp = client.get("/agents/agent-001")
        assert resp.status_code == 200
        assert resp.json()["agent_id"] == "agent-001"

    def test_get_agent_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get("/agents/ghost")
        assert resp.status_code == 404

    def test_level_thresholds_endpoint(self, client: TestClient) -> None:
        resp = client.get("/agents/meta/level-thresholds")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        # 6 levels: 0-5
        assert len(data["data"]) == 6


# ---------------------------------------------------------------------------
# /agents/{agent_id}/executions
# ---------------------------------------------------------------------------


class TestAgentExecutions:
    def _setup(self, client: TestClient, agent_id: str = "exec-agent") -> str:
        client.post(
            "/agents",
            json={"agent_id": agent_id, "description": ""},
        )
        return agent_id

    def test_record_success_execution(self, client: TestClient) -> None:
        aid = self._setup(client)
        resp = client.post(
            f"/agents/{aid}/executions",
            json={"success": True, "confidence_score": 85.0, "risk_delta": 0.1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_executions"] == 1
        assert data["successful_executions"] == 1
        assert data["success_rate"] == pytest.approx(1.0)

    def test_record_failed_execution(self, client: TestClient) -> None:
        aid = self._setup(client)
        resp = client.post(
            f"/agents/{aid}/executions",
            json={"success": False, "confidence_score": 40.0, "risk_delta": 0.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["successful_executions"] == 0
        assert data["success_rate"] == pytest.approx(0.0)

    def test_record_execution_mixed_success_rate(self, client: TestClient) -> None:
        aid = self._setup(client)
        client.post(
            f"/agents/{aid}/executions",
            json={"success": True, "confidence_score": 80.0},
        )
        client.post(
            f"/agents/{aid}/executions",
            json={"success": False, "confidence_score": 40.0},
        )
        resp = client.post(
            f"/agents/{aid}/executions",
            json={"success": True, "confidence_score": 90.0},
        )
        data = resp.json()
        assert data["total_executions"] == 3
        assert data["successful_executions"] == 2
        assert data["success_rate"] == pytest.approx(2 / 3)

    def test_record_execution_updates_avg_confidence(self, client: TestClient) -> None:
        aid = self._setup(client)
        client.post(
            f"/agents/{aid}/executions",
            json={"success": True, "confidence_score": 80.0},
        )
        resp = client.post(
            f"/agents/{aid}/executions",
            json={"success": True, "confidence_score": 60.0},
        )
        assert resp.json()["avg_confidence"] == pytest.approx(70.0)

    def test_record_execution_agent_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/agents/ghost/executions",
            json={"success": True, "confidence_score": 75.0},
        )
        assert resp.status_code == 404

    def test_record_execution_confidence_above_100_returns_422(self, client: TestClient) -> None:
        aid = self._setup(client)
        resp = client.post(
            f"/agents/{aid}/executions",
            json={"success": True, "confidence_score": 150.0},
        )
        assert resp.status_code == 422

    def test_record_execution_confidence_below_0_returns_422(self, client: TestClient) -> None:
        aid = self._setup(client)
        resp = client.post(
            f"/agents/{aid}/executions",
            json={"success": True, "confidence_score": -1.0},
        )
        assert resp.status_code == 422

    def test_record_execution_missing_success_returns_422(self, client: TestClient) -> None:
        aid = self._setup(client)
        resp = client.post(
            f"/agents/{aid}/executions",
            json={"confidence_score": 75.0},
        )
        assert resp.status_code == 422

    def test_record_multiple_executions_risk_ema(self, client: TestClient) -> None:
        """Risk score uses EMA(alpha=0.2): risk = risk*0.8 + max(0, delta)*0.2"""
        aid = self._setup(client)
        resp = client.post(
            f"/agents/{aid}/executions",
            json={"success": True, "confidence_score": 75.0, "risk_delta": 1.0},
        )
        expected_risk = 0.0 * 0.8 + 1.0 * 0.2  # = 0.2
        assert resp.json()["risk_score"] == pytest.approx(expected_risk)


# ---------------------------------------------------------------------------
# /agents/{agent_id}/promote
# ---------------------------------------------------------------------------


class TestAgentPromotion:
    def _setup(self, client: TestClient, agent_id: str = "promo-agent") -> str:
        client.post("/agents", json={"agent_id": agent_id, "description": ""})
        return agent_id

    def test_promote_agent_success(self, client: TestClient) -> None:
        aid = self._setup(client)
        resp = client.post(
            f"/agents/{aid}/promote",
            json={"new_level": 2, "reason": "earned it"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_level"] == 2
        assert any(r["level"] == 2 for r in data["promotion_history"])

    def test_promote_records_reason(self, client: TestClient) -> None:
        aid = self._setup(client)
        resp = client.post(
            f"/agents/{aid}/promote",
            json={"new_level": 1, "reason": "excellent work"},
        )
        history = resp.json()["promotion_history"]
        assert history[-1]["reason"] == "excellent work"

    def test_promote_agent_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.post(
            "/agents/ghost/promote",
            json={"new_level": 1, "reason": "x"},
        )
        assert resp.status_code == 404

    def test_promote_invalid_level_returns_422(self, client: TestClient) -> None:
        aid = self._setup(client)
        resp = client.post(
            f"/agents/{aid}/promote",
            json={"new_level": 99, "reason": "too high"},
        )
        assert resp.status_code == 422

    def test_promote_missing_reason_returns_422(self, client: TestClient) -> None:
        aid = self._setup(client)
        resp = client.post(f"/agents/{aid}/promote", json={"new_level": 1})
        assert resp.status_code == 422

    def test_promote_can_demote(self, client: TestClient) -> None:
        """new_level=0 is valid (demotion/reset)."""
        aid = self._setup(client)
        client.post(
            f"/agents/{aid}/promote",
            json={"new_level": 3, "reason": "promoted"},
        )
        resp = client.post(
            f"/agents/{aid}/promote",
            json={"new_level": 1, "reason": "violation"},
        )
        assert resp.status_code == 200
        assert resp.json()["current_level"] == 1


# ---------------------------------------------------------------------------
# /missions/{mission_id}/synthesize
# ---------------------------------------------------------------------------


class TestMissionSynthesize:
    def test_synthesize_mission_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.post("/missions/CHR-GHOST/synthesize")
        assert resp.status_code == 404

    def test_synthesize_no_events_returns_200(self, client: TestClient) -> None:
        mid = client.post("/missions", json={"objective": "synthesis test"}).json()["mission_id"]
        resp = client.post(f"/missions/{mid}/synthesize")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mission_id"] == mid
        assert "decision" in data
        assert "composite_score" in data
        assert isinstance(data["final_report"], dict)
        assert isinstance(data["next_steps"], dict)

    def test_synthesize_with_events(self, client: TestClient) -> None:
        mid = client.post("/missions", json={"objective": "synth with events"}).json()["mission_id"]
        client.post(
            f"/missions/{mid}/events",
            json={
                "magnet_name": "test",
                "inflection_point": "start",
                "observed_signal": {"x": 1},
                "risk_delta": 0.1,
                "confidence_delta": 3.0,
            },
        )
        resp = client.post(f"/missions/{mid}/synthesize")
        assert resp.status_code == 200
        assert resp.json()["mission_id"] == mid

    def test_synthesize_create_bead_param_accepted(self, client: TestClient) -> None:
        mid = client.post("/missions", json={"objective": "synth bead"}).json()["mission_id"]
        # create_bead=true is accepted; bead creation depends on orchestrator
        # returning a suggested_bead, which we do not control here.
        resp = client.post(f"/missions/{mid}/synthesize?create_bead=true")
        assert resp.status_code == 200
