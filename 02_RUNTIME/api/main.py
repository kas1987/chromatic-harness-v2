"""Chromatic Harness v2 FastAPI backend."""

import json
import sys
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

from collections import Counter
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
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
    RegisterAgentRequest,
    AgentProfileResponse,
    RecordExecutionRequest,
    PromoteAgentRequest,
    MissionAnalyticsResponse,
    TrendPoint,
    MagnetBreakdown,
    ActionCount,
    AgentLeadResponse,
    UserRegisterRequest,
    UserResponse,
    TokenResponse,
)

# Router integration — normal import because _RUNTIME is on sys.path
from router.router import ChromaticRouter  # noqa: E402
from router.contracts import (  # noqa: E402
    RouteRequest,
    TaskType,
    PrivacyClass,
    RouteConstraints,
    RouteConfidence,
    RouteAudit,
    RouteInput,
)

from auth import (  # noqa: E402
    is_auth_enabled,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

import importlib.util as _ilu  # noqa: E402


def _load_module(name: str, path: str):
    spec = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_orch_mod = _load_module(
    "chromatic_orchestrator",
    os.path.join(_RUNTIME, "orchestrator", "orchestrator.py"),
)
Orchestrator = _orch_mod.Orchestrator
MissionPacket = _orch_mod.MissionPacket

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


@app.post("/route")
async def route_request(payload: dict):
    """
    Execute a provider-neutral route through ChromaticRouter.
    Expected JSON mirrors the RouteRequest contract.
    """
    router = ChromaticRouter()
    req = RouteRequest(
        request_id=payload.get("request_id", str(uuid.uuid4())),
        task_id=payload.get("task_id", "api"),
        task_type=TaskType(payload.get("task_type", "classification")),
        objective=payload.get("objective", ""),
        input=RouteInput(
            messages=payload.get("input", {}).get("messages", []),
            files=payload.get("input", {}).get("files", []),
            metadata=payload.get("input", {}).get("metadata", {}),
        ),
        constraints=RouteConstraints(
            privacy_class=PrivacyClass(payload.get("constraints", {}).get("privacy_class", "P1")),
            max_cost_usd=payload.get("constraints", {}).get("max_cost_usd", 0.25),
            max_latency_ms=payload.get("constraints", {}).get("max_latency_ms", 30000),
            max_tokens=payload.get("constraints", {}).get("max_tokens", 8000),
            allow_cloud=payload.get("constraints", {}).get("allow_cloud", True),
            allow_broker=payload.get("constraints", {}).get("allow_broker", True),
            allow_openhuman=payload.get("constraints", {}).get("allow_openhuman", False),
            allow_tools=payload.get("constraints", {}).get("allow_tools", False),
        ),
        confidence=RouteConfidence(
            score=payload.get("confidence", {}).get("score", 75.0),
            band=payload.get("confidence", {}).get("band", "high"),
        ),
        preferred_provider=payload.get("preferred_provider", "auto"),
        fallback_chain=payload.get("fallback_chain", []),
        audit=RouteAudit(
            caller=payload.get("audit", {}).get("caller", "api"),
            repo=payload.get("audit", {}).get("repo", ""),
            human_gate_required=payload.get("audit", {}).get("human_gate_required", False),
        ),
    )
    resp = await router.route(req)
    return {
        "request_id": resp.request_id,
        "selected_provider": resp.selected_provider,
        "selected_model": resp.selected_model,
        "route_reason": resp.route_reason,
        "fallback_used": resp.fallback_used,
        "confidence_score": resp.confidence_score,
        "privacy_class": resp.privacy_class.value,
        "cost_estimate_usd": resp.cost_estimate_usd,
        "latency_ms": resp.latency_ms,
        "output": {
            "type": resp.output.type.value,
            "content": resp.output.content,
        },
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "total_tokens": resp.usage.total_tokens,
        },
        "logs": {
            "policy_checks": resp.logs.policy_checks,
            "warnings": resp.logs.warnings,
            "errors": resp.logs.errors,
        },
    }


@app.get("/auth/status")
async def auth_status():
    return {"auth_enabled": is_auth_enabled()}


@app.post("/auth/register", response_model=UserResponse, status_code=201)
async def register_user(req: UserRegisterRequest, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT user_id FROM users WHERE username = ?", (req.username,)) as cur:
        if await cur.fetchone():
            raise HTTPException(status_code=409, detail="Username already taken")
    user_id = str(uuid.uuid4())
    ts = NOW()
    hashed = hash_password(req.password)
    await db.execute(
        "INSERT INTO users (user_id, username, hashed_password, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, req.username, hashed, req.role, ts),
    )
    await db.commit()
    return UserResponse(user_id=user_id, username=req.username, role=req.role, created_at=ts)


@app.post("/auth/token", response_model=TokenResponse)
async def login(req: UserRegisterRequest, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        "SELECT user_id, hashed_password, role FROM users WHERE username = ?",
        (req.username,),
    ) as cur:
        row = await cur.fetchone()
    if not row or not verify_password(req.password, row[1]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user_id=row[0], role=row[2])  # pragma: allowlist secret
    return TokenResponse(access_token=token, user_id=row[0], role=row[2])  # pragma: allowlist secret


@app.get("/auth/me", response_model=UserResponse)
async def auth_me(
    current_user=Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Auth disabled or not authenticated")
    async with db.execute(
        "SELECT username, role, created_at FROM users WHERE user_id = ?",
        (current_user.user_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(user_id=current_user.user_id, username=row[0], role=row[1], created_at=row[2])


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
async def list_events(
    mission_id: str,
    from_ts: Optional[str] = Query(default=None, description="ISO timestamp lower bound"),
    to_ts: Optional[str] = Query(default=None, description="ISO timestamp upper bound"),
    db: aiosqlite.Connection = Depends(get_db),
):
    sql = "SELECT data FROM magnet_events WHERE mission_id = ?"
    params: list = [mission_id]
    if from_ts:
        sql += " AND created_at >= ?"
        params.append(from_ts)
    if to_ts:
        sql += " AND created_at <= ?"
        params.append(to_ts)
    sql += " ORDER BY created_at"
    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [MagnetEventResponse(**json.loads(r[0])) for r in rows]


@app.get("/missions/{mission_id}/analytics", response_model=MissionAnalyticsResponse)
async def get_mission_analytics(mission_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        "SELECT data, created_at FROM magnet_events WHERE mission_id = ? ORDER BY created_at",
        (mission_id,),
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        return MissionAnalyticsResponse(
            mission_id=mission_id,
            event_count=0,
            duration_seconds=0.0,
            confidence_trend=[],
            risk_trend=[],
            magnet_breakdown=[],
            top_actions=[],
            avg_risk_delta=0.0,
            avg_confidence_delta=0.0,
        )

    events = [json.loads(r[0]) for r in rows]
    timestamps = [r[1] for r in rows]

    # Duration
    try:
        t_first = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
        t_last = datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00"))
        duration_seconds = (t_last - t_first).total_seconds()
    except Exception:
        duration_seconds = 0.0

    # Cumulative trend lines
    cum_confidence = 0.0
    cum_risk = 0.0
    confidence_trend: list[TrendPoint] = []
    risk_trend: list[TrendPoint] = []
    for ev, ts in zip(events, timestamps):
        cum_confidence += ev.get("confidence_delta", 0.0)
        cum_risk += ev.get("risk_delta", 0.0)
        confidence_trend.append(TrendPoint(timestamp=ts, value=round(cum_confidence, 3)))
        risk_trend.append(TrendPoint(timestamp=ts, value=round(cum_risk, 3)))

    # Magnet breakdown
    magnet_stats: dict[str, dict] = {}
    for ev in events:
        name = ev.get("magnet_name", "unknown")
        if name not in magnet_stats:
            magnet_stats[name] = {"count": 0, "risk": 0.0, "confidence": 0.0}
        magnet_stats[name]["count"] += 1
        magnet_stats[name]["risk"] += ev.get("risk_delta", 0.0)
        magnet_stats[name]["confidence"] += ev.get("confidence_delta", 0.0)
    magnet_breakdown = [
        MagnetBreakdown(
            magnet_name=k,
            event_count=v["count"],
            total_risk_delta=round(v["risk"], 3),
            total_confidence_delta=round(v["confidence"], 3),
        )
        for k, v in sorted(magnet_stats.items(), key=lambda x: -x[1]["count"])
    ]

    # Top recommended actions
    action_counts = Counter(ev.get("recommended_action", "none") for ev in events)
    top_actions = [ActionCount(action=a, count=c) for a, c in action_counts.most_common(5)]

    n = len(events)
    avg_risk = sum(ev.get("risk_delta", 0.0) for ev in events) / n
    avg_conf = sum(ev.get("confidence_delta", 0.0) for ev in events) / n

    return MissionAnalyticsResponse(
        mission_id=mission_id,
        event_count=n,
        duration_seconds=round(duration_seconds, 1),
        confidence_trend=confidence_trend,
        risk_trend=risk_trend,
        magnet_breakdown=magnet_breakdown,
        top_actions=top_actions,
        avg_risk_delta=round(avg_risk, 4),
        avg_confidence_delta=round(avg_conf, 4),
    )


@app.post("/missions/{mission_id}/synthesize", response_model=AgentLeadResponse)
async def synthesize_mission(
    mission_id: str,
    auto_create_bead: bool = Query(default=False, alias="create_bead"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Run MagnetOrchestrator + Agent Lead synthesis on mission magnet events."""
    async with db.execute("SELECT data FROM missions WHERE mission_id = ?", (mission_id,)) as cur:
        mission_row = await cur.fetchone()
    if not mission_row:
        raise HTTPException(status_code=404, detail="Mission not found")

    async with db.execute(
        "SELECT data FROM magnet_events WHERE mission_id = ? ORDER BY created_at",
        (mission_id,),
    ) as cur:
        event_rows = await cur.fetchall()

    mission = json.loads(mission_row[0])
    events = [json.loads(r[0]) for r in event_rows]

    orch = Orchestrator()
    packet = MissionPacket(
        mission_id=mission["mission_id"],
        objective=mission["objective"],
        agent_role=mission.get("agent_role", "agent_lead"),
        autonomy_level=mission.get("autonomy_level", "L1"),
        confidence_required=mission.get("confidence_required", 75.0),
        allowed_tools=mission.get("allowed_tools", []),
        stop_conditions=mission.get("stop_conditions", []),
        required_outputs=mission.get("required_outputs", []),
    )
    output = orch.synthesize_mission(packet, events)

    bead_created = None
    if auto_create_bead and output.suggested_bead:
        sb = output.suggested_bead
        bead_req = CreateBeadRequest(
            title=sb["title"],
            objective=sb["objective"],
            priority=sb.get("priority", "p2"),
            source=sb.get("source", "agent_lead"),
            mission_id=mission_id,
        )
        bead_created = await create_bead(bead_req, db)

    return AgentLeadResponse(
        mission_id=mission_id,
        decision=output.decision,
        composite_score=output.composite_score,
        final_report=output.final_report,
        pr_package=output.pr_package,
        next_steps=output.next_steps,
        audit_log=output.audit_log,
        handoff_prep=output.handoff_prep,
        suggested_bead=output.suggested_bead,
        bead_created=bead_created,
    )


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


# ─── Agent Profiles ───────────────────────────────────────────────────────────

_LEVEL_THRESHOLDS = {
    0: {"min_executions": 0, "min_success_rate": 0.0, "max_risk": 1.0},
    1: {"min_executions": 5, "min_success_rate": 0.70, "max_risk": 0.6},
    2: {"min_executions": 20, "min_success_rate": 0.80, "max_risk": 0.45},
    3: {"min_executions": 50, "min_success_rate": 0.88, "max_risk": 0.30},
    4: {"min_executions": 100, "min_success_rate": 0.93, "max_risk": 0.20},
    5: {"min_executions": 200, "min_success_rate": 0.97, "max_risk": 0.10},
}


def _agent_data_to_response(data: dict) -> AgentProfileResponse:
    total = data.get("total_executions", 0)
    success = data.get("successful_executions", 0)
    data["success_rate"] = (success / total) if total > 0 else 0.0
    return AgentProfileResponse(**data)


@app.post("/agents", response_model=AgentProfileResponse, status_code=201)
async def register_agent(req: RegisterAgentRequest, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT data FROM agent_profiles WHERE agent_id = ?", (req.agent_id,)) as cur:
        existing = await cur.fetchone()
    if existing:
        raise HTTPException(status_code=409, detail=f"Agent {req.agent_id!r} already registered")

    ts = NOW()
    data = {
        "agent_id": req.agent_id,
        "description": req.description,
        "current_level": req.initial_level,
        "total_executions": 0,
        "successful_executions": 0,
        "success_rate": 0.0,
        "avg_confidence": 0.0,
        "risk_score": 0.0,
        "promotion_history": [{"level": req.initial_level, "date": ts, "reason": "initial registration"}]
        if req.initial_level > 0
        else [],
        "last_violation": None,
        "created_at": ts,
        "updated_at": ts,
    }
    await db.execute(
        "INSERT INTO agent_profiles (agent_id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (req.agent_id, json.dumps(data), ts, ts),
    )
    await db.commit()
    return _agent_data_to_response(data)


@app.get("/agents", response_model=list[AgentProfileResponse])
async def list_agents(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT data FROM agent_profiles ORDER BY created_at DESC") as cur:
        rows = await cur.fetchall()
    return [_agent_data_to_response(json.loads(r[0])) for r in rows]


@app.get("/agents/{agent_id}", response_model=AgentProfileResponse)
async def get_agent(agent_id: str, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("SELECT data FROM agent_profiles WHERE agent_id = ?", (agent_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")
    return _agent_data_to_response(json.loads(row[0]))


@app.post("/agents/{agent_id}/executions", response_model=AgentProfileResponse)
async def record_execution(
    agent_id: str,
    req: RecordExecutionRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT data FROM agent_profiles WHERE agent_id = ?", (agent_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")

    data = json.loads(row[0])
    data["total_executions"] += 1
    if req.success:
        data["successful_executions"] += 1
    total = data["total_executions"]
    data["success_rate"] = data["successful_executions"] / total
    # Running average for confidence
    prev_avg = data.get("avg_confidence", 0.0)
    data["avg_confidence"] = prev_avg + (req.confidence_score - prev_avg) / total
    # Risk score: exponential moving average (alpha=0.2)
    data["risk_score"] = max(0.0, min(1.0, data["risk_score"] * 0.8 + max(0.0, req.risk_delta) * 0.2))
    ts = NOW()
    data["updated_at"] = ts
    await db.execute(
        "UPDATE agent_profiles SET data = ?, updated_at = ? WHERE agent_id = ?",
        (json.dumps(data), ts, agent_id),
    )
    await db.commit()
    return _agent_data_to_response(data)


@app.post("/agents/{agent_id}/promote", response_model=AgentProfileResponse)
async def promote_agent(
    agent_id: str,
    req: PromoteAgentRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT data FROM agent_profiles WHERE agent_id = ?", (agent_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} not found")

    data = json.loads(row[0])
    ts = NOW()
    data["promotion_history"].append({"level": req.new_level, "date": ts, "reason": req.reason})
    data["current_level"] = req.new_level
    data["updated_at"] = ts
    await db.execute(
        "UPDATE agent_profiles SET data = ?, updated_at = ? WHERE agent_id = ?",
        (json.dumps(data), ts, agent_id),
    )
    await db.commit()
    return _agent_data_to_response(data)


@app.get("/agents/meta/level-thresholds")
async def level_thresholds():
    return {"data": _LEVEL_THRESHOLDS}


async def _route_for_mission(mission: Any, task_type: str = "planning") -> dict:
    """Route a MissionPacket through ChromaticRouter and return a summary dict."""
    router = ChromaticRouter()
    req = RouteRequest(
        request_id=str(uuid.uuid4()),
        task_id=getattr(mission, "mission_id", "unknown"),
        task_type=TaskType(task_type),
        objective=getattr(mission, "objective", ""),
        input=RouteInput(
            messages=getattr(mission, "messages", []),
            files=getattr(mission, "files", []),
            metadata=getattr(mission, "metadata", {}),
        ),
        constraints=RouteConstraints(
            privacy_class=PrivacyClass(getattr(mission, "privacy_class", "P1")) if isinstance(getattr(mission, "privacy_class", None), str) else getattr(mission, "privacy_class", PrivacyClass.P1),
            max_cost_usd=getattr(mission, "max_cost_usd", 0.25),
        ),
    )
    resp = await router.route(req)
    return {
        "provider": resp.selected_provider,
        "model": resp.selected_model,
        "task_type": task_type,
        "mission_id": getattr(mission, "mission_id", None),
    }
