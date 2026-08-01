"""Integration tests for Auth + RBAC (bead k6d).

Run with AUTH_ENABLED=true to exercise the full auth path.
Without it, endpoints still respond but token validation is skipped.

Isolation strategy: each test gets a fresh in-memory SQLite DB via a
dependency override on get_db, identical to the pattern used in
tests/02_RUNTIME/api/test_api_endpoints.py. This avoids any cross-test
or cross-file DB state contamination in the full suite.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ["AUTH_ENABLED"] = "true"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02_RUNTIME", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02_RUNTIME"))

import aiosqlite  # noqa: E402
from main import app, get_db  # noqa: E402

# ---------------------------------------------------------------------------
# In-memory DB helper (mirrors test_api_endpoints.py pattern)
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

_db_conn: aiosqlite.Connection | None = None


async def _make_db() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    for stmt in _CREATE_TABLES:
        await conn.execute(stmt)
    await conn.commit()
    return conn


async def _override_get_db():
    global _db_conn
    assert _db_conn is not None, "_db_conn not initialised by fixture"
    yield _db_conn


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    """AsyncClient backed by a fresh in-memory SQLite DB for each test."""
    global _db_conn
    _db_conn = await _make_db()
    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    await _db_conn.close()
    _db_conn = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_status_enabled(client):
    resp = await client.get("/auth/status")
    assert resp.status_code == 200
    assert resp.json()["auth_enabled"] is True


@pytest.mark.asyncio
async def test_register_user(client):
    resp = await client.post(
        "/auth/register",
        json={"username": "alice", "password": "secret", "role": "reviewer"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "alice"
    assert body["role"] == "reviewer"
    assert "user_id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_register_duplicate_rejected(client):
    await client.post("/auth/register", json={"username": "bob", "password": "pw"})
    resp = await client.post("/auth/register", json={"username": "bob", "password": "pw2"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_token(client):
    await client.post("/auth/register", json={"username": "carol", "password": "mypass"})
    resp = await client.post("/auth/token", json={"username": "carol", "password": "mypass"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert "user_id" in body


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/auth/register", json={"username": "dave", "password": "correct"})
    resp = await client.post("/auth/token", json={"username": "dave", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    resp = await client.post("/auth/token", json={"username": "ghost", "password": "pw"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_with_valid_token(client):
    await client.post("/auth/register", json={"username": "eve", "password": "pw", "role": "admin"})
    token_resp = await client.post("/auth/token", json={"username": "eve", "password": "pw"})
    token = token_resp.json()["access_token"]

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "eve"
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_auth_me_no_token(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_invalid_token(client):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_default_role_is_executor(client):
    resp = await client.post("/auth/register", json={"username": "frank", "password": "pw"})
    assert resp.status_code == 201
    assert resp.json()["role"] == "executor"
