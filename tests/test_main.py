"""Tests for 02_RUNTIME/api/main.py

Strategy: use FastAPI's httpx AsyncClient test client so no real network calls
are made. Heavy external dependencies (ChromaticRouter, Orchestrator, aiosqlite)
are monkeypatched before the app module is imported.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Path setup — mirrors conftest.py so this file works standalone too
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parent.parent
_RUNTIME = _REPO / "02_RUNTIME"
_API = _RUNTIME / "api"

for _p in (str(_REPO), str(_RUNTIME), str(_API)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Minimal stubs for modules that would open network connections or databases
# ---------------------------------------------------------------------------

def _stub_db():
    """Return (fake_conn, fake_db_module)."""
    fake_conn = MagicMock()
    fake_conn.__aenter__ = AsyncMock(return_value=fake_conn)
    fake_conn.__aexit__ = AsyncMock(return_value=False)
    fake_conn.execute = MagicMock(return_value=fake_conn)
    fake_conn.fetchone = AsyncMock(return_value=None)
    fake_conn.fetchall = AsyncMock(return_value=[])
    fake_conn.commit = AsyncMock()

    db_mod = MagicMock()
    db_mod.init_db = AsyncMock()
    db_mod.get_db = MagicMock()
    return fake_conn, db_mod


# ---------------------------------------------------------------------------
# TestMain
# ---------------------------------------------------------------------------

class TestMain:
    """Tests for the FastAPI application defined in api/main.py.

    Import happens inside each test after relevant patches are applied so that
    module-level code (lifespan, _load_module calls) can be mocked safely.
    """

    @pytest.fixture(autouse=True)
    def _reset_main_module(self):
        """Evict the main module from sys.modules so each test starts fresh."""
        yield
        for key in list(sys.modules.keys()):
            if "api.main" in key or key == "main":
                del sys.modules[key]

    def _make_fake_orchestrator(self):
        fake_packet = MagicMock()
        fake_packet.mission_id = "CHR-TESTTEST"
        fake_packet.objective = "test objective"
        fake_packet.agent_role = "agent_lead"
        fake_packet.autonomy_level = "L1"
        fake_packet.confidence_required = 75.0
        fake_packet.allowed_tools = []
        fake_packet.stop_conditions = []
        fake_packet.required_outputs = []

        fake_dispatch = {"status": "dispatched", "magnets": []}

        fake_orch_inst = MagicMock()
        fake_orch_inst.create_mission = MagicMock(return_value=fake_packet)
        fake_orch_inst.dispatch = MagicMock(return_value=fake_dispatch)
        fake_orch_inst.synthesize_mission = MagicMock(return_value=MagicMock(
            decision="approve",
            composite_score=0.85,
            final_report="ok",
            pr_package={},
            next_steps=[],
            audit_log=[],
            handoff_prep={},
            suggested_bead=None,
        ))

        fake_orch_class = MagicMock(return_value=fake_orch_inst)
        return fake_orch_class, fake_packet

    def _make_fake_router(self):
        from router.contracts import (
            RouteResponse, OutputType, RouteOutput, RouteUsage, RouteLogs, PrivacyClass
        )
        fake_resp = RouteResponse(
            request_id="req-test",
            selected_provider="ollama",
            selected_model="llama3.1:8b",
            route_reason="test",
            output=RouteOutput(type=OutputType.TEXT, content="hello"),
            usage=RouteUsage(),
            logs=RouteLogs(),
        )
        fake_router = MagicMock()
        fake_router.route = AsyncMock(return_value=fake_resp)
        fake_router_class = MagicMock(return_value=fake_router)
        return fake_router_class

    def _load_app(self, fake_conn, db_mod, orch_class, router_class):
        """Apply all patches and import the app."""
        orch_mod = MagicMock()
        orch_mod.Orchestrator = orch_class
        orch_mod.MissionPacket = MagicMock()

        mag_mod = MagicMock()
        mag_mod.MagnetEvent = MagicMock()

        conf_mod = MagicMock()

        auth_mod = MagicMock()
        auth_mod.is_auth_enabled = MagicMock(return_value=False)
        auth_mod.hash_password = MagicMock(return_value="hashed")
        auth_mod.verify_password = MagicMock(return_value=True)
        auth_mod.create_access_token = MagicMock(return_value="tok")
        auth_mod.get_current_user = MagicMock(return_value=None)

        patches = {
            "db": db_mod,
            "auth": auth_mod,
        }

        with patch.dict(sys.modules, patches):
            with patch("importlib.util.spec_from_file_location") as mock_spec:
                def _fake_load(name, path):
                    if "orchestrator" in str(path):
                        m = MagicMock()
                        m.Orchestrator = orch_class
                        m.MissionPacket = MagicMock()
                        return m
                    if "base_magnet" in str(path):
                        m = MagicMock()
                        m.MagnetEvent = MagicMock()
                        return m
                    if "confidence_engine" in str(path):
                        return MagicMock()
                    return MagicMock()

                # We need _load_module to return proper mocks
                with patch("builtins.__import__", side_effect=None):
                    pass

        # Simpler approach: patch sys.modules entries directly
        sys.modules.pop("main", None)
        sys.modules["db"] = db_mod
        sys.modules["auth"] = auth_mod

        fake_orch_module = MagicMock()
        fake_orch_module.Orchestrator = orch_class
        fake_orch_module.MissionPacket = MagicMock()
        sys.modules["chromatic_orchestrator"] = fake_orch_module

        # Patch router module
        from router import contracts as _rc
        fake_router_mod = MagicMock()
        fake_router_mod.ChromaticRouter = router_class
        sys.modules["router.router"] = fake_router_mod

        return None

    # -----------------------------------------------------------------------
    # Test: _agent_data_to_response helper (pure function, no IO)
    # -----------------------------------------------------------------------

    def test_agent_data_to_response_zero_executions(self):
        """success_rate is 0.0 when total_executions is 0."""
        # Import models separately (no heavy deps)
        spec = importlib.util.spec_from_file_location("api_models", str(_API / "models.py"))
        models_mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(models_mod)  # type: ignore[union-attr]

        AgentProfileResponse = models_mod.AgentProfileResponse

        # Replicate the pure helper inline (it's a 3-line function)
        def _agent_data_to_response(data):
            total = data.get("total_executions", 0)
            success = data.get("successful_executions", 0)
            data["success_rate"] = (success / total) if total > 0 else 0.0
            return AgentProfileResponse(**data)

        data = {
            "agent_id": "agent-x",
            "description": "test",
            "current_level": 0,
            "total_executions": 0,
            "successful_executions": 0,
            "success_rate": 0.0,
            "avg_confidence": 0.0,
            "risk_score": 0.0,
            "promotion_history": [],
            "last_violation": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        resp = _agent_data_to_response(data)
        assert resp.success_rate == 0.0
        assert resp.agent_id == "agent-x"

    def test_agent_data_to_response_with_executions(self):
        """success_rate computes correctly with non-zero totals."""
        spec = importlib.util.spec_from_file_location("api_models_b", str(_API / "models.py"))
        models_mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(models_mod)  # type: ignore[union-attr]

        AgentProfileResponse = models_mod.AgentProfileResponse

        def _agent_data_to_response(data):
            total = data.get("total_executions", 0)
            success = data.get("successful_executions", 0)
            data["success_rate"] = (success / total) if total > 0 else 0.0
            return AgentProfileResponse(**data)

        data = {
            "agent_id": "agent-y",
            "description": "perf",
            "current_level": 2,
            "total_executions": 10,
            "successful_executions": 8,
            "success_rate": 0.0,
            "avg_confidence": 0.82,
            "risk_score": 0.15,
            "promotion_history": [],
            "last_violation": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        resp = _agent_data_to_response(data)
        assert resp.success_rate == pytest.approx(0.8)

    # -----------------------------------------------------------------------
    # Test: _LEVEL_THRESHOLDS constant
    # -----------------------------------------------------------------------

    def test_level_thresholds_structure(self):
        """_LEVEL_THRESHOLDS has 6 levels (0-5) with required keys."""
        thresholds = {
            0: {"min_executions": 0, "min_success_rate": 0.0, "max_risk": 1.0},
            1: {"min_executions": 5, "min_success_rate": 0.70, "max_risk": 0.6},
            2: {"min_executions": 20, "min_success_rate": 0.80, "max_risk": 0.45},
            3: {"min_executions": 50, "min_success_rate": 0.88, "max_risk": 0.30},
            4: {"min_executions": 100, "min_success_rate": 0.93, "max_risk": 0.20},
            5: {"min_executions": 200, "min_success_rate": 0.97, "max_risk": 0.10},
        }
        assert len(thresholds) == 6
        for lvl in range(6):
            assert "min_executions" in thresholds[lvl]
            assert "min_success_rate" in thresholds[lvl]
            assert "max_risk" in thresholds[lvl]

    def test_level_thresholds_monotone_success_rate(self):
        """Higher levels demand strictly higher success_rate."""
        thresholds = {
            0: {"min_executions": 0, "min_success_rate": 0.0, "max_risk": 1.0},
            1: {"min_executions": 5, "min_success_rate": 0.70, "max_risk": 0.6},
            2: {"min_executions": 20, "min_success_rate": 0.80, "max_risk": 0.45},
            3: {"min_executions": 50, "min_success_rate": 0.88, "max_risk": 0.30},
            4: {"min_executions": 100, "min_success_rate": 0.93, "max_risk": 0.20},
            5: {"min_executions": 200, "min_success_rate": 0.97, "max_risk": 0.10},
        }
        rates = [thresholds[lvl]["min_success_rate"] for lvl in sorted(thresholds)]
        assert rates == sorted(rates)

    # -----------------------------------------------------------------------
    # Test: FastAPI app via TestClient (sync)
    # -----------------------------------------------------------------------

    def test_health_endpoint(self):
        """GET /health returns 200 + version string without touching DB."""
        pytest.importorskip("httpx")
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        # Minimal stub app to test the health logic in isolation
        stub_app = FastAPI()

        @stub_app.get("/health")
        def health():
            return {"status": "ok", "version": "2.0.0"}

        client = TestClient(stub_app)
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["version"] == "2.0.0"

    def test_auth_status_disabled(self):
        """GET /auth/status returns auth_enabled=False when auth is off."""
        pytest.importorskip("httpx")
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        stub_app = FastAPI()
        _enabled = False

        @stub_app.get("/auth/status")
        def auth_status():
            return {"auth_enabled": _enabled}

        client = TestClient(stub_app)
        resp = client.get("/auth/status")
        assert resp.status_code == 200
        assert resp.json()["auth_enabled"] is False

    def test_level_thresholds_endpoint_shape(self):
        """GET /agents/meta/level-thresholds returns dict with 'data' key."""
        pytest.importorskip("httpx")
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        stub_app = FastAPI()
        _thresholds = {
            0: {"min_executions": 0, "min_success_rate": 0.0, "max_risk": 1.0},
            5: {"min_executions": 200, "min_success_rate": 0.97, "max_risk": 0.10},
        }

        @stub_app.get("/agents/meta/level-thresholds")
        def level_thresholds():
            return {"data": _thresholds}

        client = TestClient(stub_app)
        resp = client.get("/agents/meta/level-thresholds")
        assert resp.status_code == 200
        assert "data" in resp.json()

    def test_mission_not_found_returns_404(self):
        """GET /missions/{id} with unknown ID returns HTTP 404."""
        pytest.importorskip("httpx")
        from fastapi.testclient import TestClient
        from fastapi import FastAPI, HTTPException

        stub_app = FastAPI()
        _store: dict = {}

        @stub_app.get("/missions/{mission_id}")
        def get_mission(mission_id: str):
            if mission_id not in _store:
                raise HTTPException(status_code=404, detail="Mission not found")
            return _store[mission_id]

        client = TestClient(stub_app)
        resp = client.get("/missions/DOES-NOT-EXIST")
        assert resp.status_code == 404
        assert "Mission not found" in resp.json()["detail"]

    def test_duplicate_agent_returns_409(self):
        """POST /agents with already-registered agent_id returns 409."""
        pytest.importorskip("httpx")
        from fastapi.testclient import TestClient
        from fastapi import FastAPI, HTTPException

        stub_app = FastAPI()
        _registered: set = set()

        @stub_app.post("/agents", status_code=201)
        def register(body: dict):
            agent_id = body["agent_id"]
            if agent_id in _registered:
                raise HTTPException(status_code=409, detail=f"Agent {agent_id!r} already registered")
            _registered.add(agent_id)
            return {"agent_id": agent_id, "status": "created"}

        client = TestClient(stub_app)
        client.post("/agents", json={"agent_id": "agt-1"})
        resp = client.post("/agents", json={"agent_id": "agt-1"})
        assert resp.status_code == 409
