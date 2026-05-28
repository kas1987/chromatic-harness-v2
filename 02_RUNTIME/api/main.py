"""Chromatic Harness v2 FastAPI backend."""

import json
import sys
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

from fastapi import FastAPI, HTTPException, Depends
import aiosqlite

_HERE = os.path.dirname(os.path.abspath(__file__))
_RUNTIME = os.path.dirname(_HERE)
_REPO = os.path.dirname(_RUNTIME)
sys.path.insert(0, _REPO)
sys.path.insert(0, _RUNTIME)
sys.path.insert(0, _HERE)

from db import init_db, get_db  # noqa: E402
from models import (  # noqa: E402
    CreateMissionRequest,
    MissionResponse,
    CreateEventRequest,
    MagnetEventResponse,
    CreateBeadRequest,
    BeadResponse,
)

import importlib.util as _ilu


def _load_module(name: str, path: str):
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_orch_mod = _load_module("orchestrator", os.path.join(_RUNTIME, "orchestrator", "orchestrator.py"))
Orchestrator = _orch_mod.Orchestrator

_mag_mod = _load_module("base_magnet", os.path.join(_RUNTIME, "magnets", "base_magnet.py"))
MagnetEvent = _mag_mod.MagnetEvent

_conf_mod = _load_module("confidence_engine", os.path.join(_RUNTIME, "orchestrator", "confidence_engine.py"))

NOW = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Chromatic Harness v2 API", version="2.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/missions", response_model=MissionResponse)
async def create_mission(req: CreateMissionRequest, db: aiosqlite.Connection = Depends(get_db)):
    orch = Orchestrator()
    packet = orch.create_mission(req.objective)
    packet.mission_id = f"CHR-{str(uuid.uuid4())[:8].upper()}"
    packet.agent_role = req.agent_role
    packet.autonomy_level = req.autonomy_level
    packet.confidence_required = req.confidence_required
    packet.allowed_tools = req.allowed_tools or packet.allowed_tools
    packet.stop_conditions = req.stop_conditions or packet.stop_conditions
    packet.required_outputs = req.required_outputs or packet.required_outputs
    dispatch = orch.dispatch(packet)
    data = {
        "mission_id": packet.mission_id,
        "objective": packet.objective,
        "agent_role": packet.agent_role,
        "autonomy_level": packet.autonomy_level,
        "confidence_required": packet.confidence_required,
        "allowed_tools": packet.allowed_tools,
        "stop_conditions": packet.stop_conditions,
        "required_outputs": packet.required_outputs,
        "status": dispatch["status"],
        "magnets": dispatch["magnets"],
    }
    await db.execute(
        "INSERT INTO missions (mission_id, data, created_at) VALUES (?, ?, ?)",
        (packet.mission_id, json.dumps(data), NOW()),
    )
    await db.commit()
    return MissionResponse(**data)


@app.get("/missions", response_model=list[MissionResponse])
async def list_missions(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT data FROM missions ORDER BY created_at DESC") as cur:
        rows = await cur.fetchall()
    return [MissionResponse(**json.loads(r[0])) for r in rows]


@app.get("/missions/{mission_id}", response_model=MissionResponse)
async def get_mission(mission_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT data FROM missions WHERE mission_id = ?", (mission_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Mission not found")
    return MissionResponse(**json.loads(row[0]))


@app.post("/missions/{mission_id}/events", response_model=MagnetEventResponse)
async def create_event(mission_id: str, req: CreateEventRequest, db: aiosqlite.Connection = Depends(get_db)):
    event_id = str(uuid.uuid4())
    ts = NOW()
    data = {
        "event_id": event_id,
        "mission_id": mission_id,
        "magnet_name": req.magnet_name,
        "inflection_point": req.inflection_point,
        "observed_signal": req.observed_signal,
        "risk_delta": req.risk_delta,
        "confidence_delta": req.confidence_delta,
        "evidence": req.evidence,
        "recommended_action": req.recommended_action,
        "timestamp": ts,
    }
    await db.execute(
        "INSERT INTO magnet_events (event_id, mission_id, data, created_at) VALUES (?, ?, ?, ?)",
        (event_id, mission_id, json.dumps(data), ts),
    )
    await db.commit()
    return MagnetEventResponse(**data)


@app.get("/missions/{mission_id}/events", response_model=list[MagnetEventResponse])
async def list_events(mission_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        "SELECT data FROM magnet_events WHERE mission_id = ? ORDER BY created_at", (mission_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [MagnetEventResponse(**json.loads(r[0])) for r in rows]


@app.post("/beads", response_model=BeadResponse)
async def create_bead(req: CreateBeadRequest, db: aiosqlite.Connection = Depends(get_db)):
    bead_id = f"BEAD-{str(uuid.uuid4())[:8].upper()}"
    ts = NOW()
    data = {
        "bead_id": bead_id,
        "title": req.title,
        "objective": req.objective,
        "priority": req.priority,
        "status": "created",
        "source": req.source,
        "mission_id": req.mission_id,
        "created_at": ts,
    }
    await db.execute(
        "INSERT INTO beads (bead_id, mission_id, data, created_at) VALUES (?, ?, ?, ?)",
        (bead_id, req.mission_id, json.dumps(data), ts),
    )
    await db.commit()
    return BeadResponse(**data)


@app.get("/beads", response_model=list[BeadResponse])
async def list_beads(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT data FROM beads ORDER BY created_at DESC") as cur:
        rows = await cur.fetchall()
    return [BeadResponse(**json.loads(r[0])) for r in rows]
