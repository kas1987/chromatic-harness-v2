"""Integration tests for Auth + RBAC (bead k6d).

Run with AUTH_ENABLED=true to exercise the full auth path.
Without it, endpoints still respond but token validation is skipped.
"""

import os
import tempfile
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ["AUTH_ENABLED"] = "true"

_tmp_db = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
_tmp_db.close()
os.environ["CHROMATIC_DB_PATH"] = _tmp_db.name

import sys  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02_RUNTIME", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02_RUNTIME"))

from main import app  # noqa: E402
from db import init_db  # noqa: E402
import auth as auth_module  # noqa: E402


@pytest_asyncio.fixture
async def client():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_auth_status_enabled(client):
    resp = await client.get("/auth/status")
    assert resp.status_code == 200
    assert resp.json()["auth_enabled"] is True


@pytest.mark.asyncio
async def test_register_rejects_elevated_role(client):
    resp = await client.post(
        "/auth/register",
        json={"username": "alice", "password": "secret", "role": "reviewer"},
    )
    assert resp.status_code == 403


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
    await client.post("/auth/register", json={"username": "eve", "password": "pw"})
    token_resp = await client.post("/auth/token", json={"username": "eve", "password": "pw"})
    token = token_resp.json()["access_token"]  # pragma: allowlist secret

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "eve"
    assert resp.json()["role"] == "executor"


@pytest.mark.asyncio
async def test_auth_me_no_token(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_invalid_token(client):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_rejects_invalid_signed_claims(client):
    await client.post("/auth/register", json={"username": "claims", "password": "pw"})
    token = auth_module.create_access_token("claims", "invalid-role")  # pragma: allowlist secret
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_default_role_is_executor(client):
    resp = await client.post("/auth/register", json={"username": "frank", "password": "pw"})
    assert resp.status_code == 201
    assert resp.json()["role"] == "executor"


def test_production_requires_strong_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_SECRET_KEY", "too-short")
    with pytest.raises(RuntimeError, match="32 bytes"):
        auth_module._require_secure_secret()

    monkeypatch.setenv("AUTH_SECRET_KEY", "x" * 32)
    auth_module._require_secure_secret()
