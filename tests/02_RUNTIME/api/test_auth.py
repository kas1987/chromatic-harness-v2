"""Unit tests for 02_RUNTIME/api/auth.py.

Tests cover:
- is_auth_enabled() env-var toggling
- hash_password / verify_password (bcrypt wrappers)
- create_access_token / decode_token (JWT round-trip, expiry, tamper)
- CurrentUser: has_role / require_role RBAC hierarchy
- get_current_user FastAPI dependency (auth disabled, missing token, valid token)
- require_admin / require_reviewer / require_executor dependencies
- Behaviour when jose / bcrypt are unavailable (_DEPS_AVAILABLE = False path)

# DEFICIENCIES NOTED
# 1. SECRET_KEY is read at module import time from os.environ, so tests that need a
#    custom key must monkeypatch auth.SECRET_KEY directly (not just the env-var).
# 2. ACCESS_TOKEN_EXPIRE_MINUTES is also a module-level constant; expiry-edge tests
#    that want a short TTL must either monkeypatch the constant or create a token
#    with a manually back-dated `exp` claim and call jwt.decode directly.
# 3. The module uses `from jose import JWTError, jwt` inside a try/except, so the
#    real jose library must be available (or shimmed) for most tests; the shim from
#    test_api_endpoints.py is replicated here with a real-exception JWTError.
# 4. get_current_user is an async FastAPI dependency; it is tested here by calling
#    it directly with `await`, which requires asyncio_mode = strict (set in pytest.ini).
"""

from __future__ import annotations

import sys
import types
import unittest.mock as mock
from datetime import datetime, timedelta, timezone

import pytest

# ---------------------------------------------------------------------------
# Shim jose + bcrypt BEFORE importing auth so C-extensions are not required.
# Mirror the same shim approach used in test_api_endpoints.py.
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

# JWTError must be a real exception class so `except JWTError` works.
sys.modules["jose"].JWTError = Exception

import base64 as _base64  # noqa: E402

_jose_jwt_mock = mock.MagicMock()


def _jwt_encode(payload: dict, key: str, algorithm: str = "HS256") -> str:
    import json as _json

    data = _json.dumps(payload).encode()
    return "mock." + _base64.b64encode(data).decode()


def _jwt_decode(token: str, key: str, algorithms: list) -> dict:  # pragma: allowlist secret
    if not token.startswith("mock."):
        raise Exception("Invalid token")
    import json as _json

    data = _base64.b64decode(token[5:]).decode()
    payload = _json.loads(data)
    # Honour exp claim — raise JWTError (shimmed as Exception) if expired.
    exp = payload.get("exp")
    if exp is not None:
        if isinstance(exp, (int, float)):
            exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
        else:
            exp_dt = exp  # already datetime
        if datetime.now(timezone.utc) > exp_dt:
            raise Exception("Token expired")
    return payload


_jose_jwt_mock.encode = _jwt_encode
_jose_jwt_mock.decode = _jwt_decode
sys.modules["jose"].jwt = _jose_jwt_mock
sys.modules["jose.jwt"] = _jose_jwt_mock

# bcrypt mock: deterministic plain-text scheme
_bcrypt_mock = mock.MagicMock()


def _hashpw(plain_bytes: bytes, salt: bytes) -> bytes:
    return b"plain:" + plain_bytes


def _checkpw(plain_bytes: bytes, hashed_bytes: bytes) -> bool:
    return hashed_bytes == b"plain:" + plain_bytes


_bcrypt_mock.hashpw = _hashpw
_bcrypt_mock.gensalt = lambda: b"fakesalt"
_bcrypt_mock.checkpw = _checkpw
sys.modules["bcrypt"] = _bcrypt_mock

# ---------------------------------------------------------------------------
# Now safe to import the auth module.
# ---------------------------------------------------------------------------
from fastapi import HTTPException  # noqa: E402

import auth  # noqa: E402
from auth import (  # noqa: E402
    CurrentUser,
    Role,
    _ROLE_RANK,
    create_access_token,
    decode_token,
    get_current_user,
    hash_password,
    is_auth_enabled,
    require_admin,
    require_executor,
    require_reviewer,
    verify_password,
)


# ---------------------------------------------------------------------------
# is_auth_enabled
# ---------------------------------------------------------------------------


class TestIsAuthEnabled:
    def test_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AUTH_ENABLED", raising=False)
        assert is_auth_enabled() is False

    def test_enabled_when_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_ENABLED", "true")
        assert is_auth_enabled() is True

    def test_enabled_case_insensitive_TRUE(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_ENABLED", "TRUE")
        assert is_auth_enabled() is True

    def test_disabled_when_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_ENABLED", "false")
        assert is_auth_enabled() is False

    def test_disabled_for_arbitrary_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_ENABLED", "yes")
        assert is_auth_enabled() is False


# ---------------------------------------------------------------------------
# hash_password / verify_password
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_password_returns_string(self) -> None:
        hashed = hash_password("secret")  # pragma: allowlist secret
        assert isinstance(hashed, str)

    def test_verify_password_correct(self) -> None:
        hashed = hash_password("mypassword")  # pragma: allowlist secret
        assert verify_password("mypassword", hashed) is True  # pragma: allowlist secret

    def test_verify_password_wrong(self) -> None:
        hashed = hash_password("correct")  # pragma: allowlist secret
        assert verify_password("wrong", hashed) is False  # pragma: allowlist secret

    def test_verify_password_empty_plain_fails(self) -> None:
        hashed = hash_password("secret")  # pragma: allowlist secret
        assert verify_password("", hashed) is False

    def test_hash_uses_bcrypt_hashpw(self) -> None:
        # The shim encodes as "plain:<password>" so the prefix is detectable.
        hashed = hash_password("abc")
        assert hashed.startswith("plain:")

    def test_verify_password_returns_false_when_bcrypt_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(auth, "_BCRYPT_AVAILABLE", False)
        # verify_password returns False when bcrypt is unavailable
        assert verify_password("any", "any") is False

    def test_hash_password_raises_when_bcrypt_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(auth, "_BCRYPT_AVAILABLE", False)
        with pytest.raises(RuntimeError, match="bcrypt not installed"):
            hash_password("secret")  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# create_access_token / decode_token
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    def test_returns_string(self) -> None:
        jwt_str = create_access_token("user-1", "admin")
        assert isinstance(jwt_str, str)
        assert len(jwt_str) > 0

    def test_token_is_decodable(self) -> None:
        jwt_str = create_access_token("alice", "reviewer")
        payload = decode_token(jwt_str)
        assert payload["sub"] == "alice"
        assert payload["role"] == "reviewer"

    def test_token_contains_exp(self) -> None:
        jwt_str = create_access_token("u", "executor")
        payload = decode_token(jwt_str)
        assert "exp" in payload

    def test_create_raises_when_deps_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(auth, "_DEPS_AVAILABLE", False)
        with pytest.raises(RuntimeError, match="python-jose not installed"):
            create_access_token("u", "admin")

    def test_different_roles_encoded_correctly(self) -> None:
        for role in ("admin", "reviewer", "executor"):
            jwt_str = create_access_token("u", role)
            payload = decode_token(jwt_str)
            assert payload["role"] == role


class TestDecodeToken:
    def test_invalid_token_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            decode_token("not.a.valid.token")
        assert exc_info.value.status_code == 401

    def test_tampered_token_raises_401(self) -> None:
        """A token that doesn't start with 'mock.' will fail decoding."""
        with pytest.raises(HTTPException) as exc_info:
            decode_token("Bearer eyJhbGciOiJIUzI1NiJ9.tampered.sig")
        assert exc_info.value.status_code == 401

    def test_expired_token_raises_401(self) -> None:
        """Manually build a token with exp in the past."""
        import json as _json

        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        payload = {"sub": "ghost", "role": "executor", "exp": past.timestamp()}
        raw = _json.dumps(payload).encode()
        expired_token = "mock." + _base64.b64encode(raw).decode()
        with pytest.raises(HTTPException) as exc_info:
            decode_token(expired_token)
        assert exc_info.value.status_code == 401

    def test_decode_raises_when_deps_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(auth, "_DEPS_AVAILABLE", False)
        with pytest.raises(RuntimeError, match="python-jose not installed"):
            decode_token("any-token")

    def test_detail_message_on_invalid_token(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            decode_token("garbage")
        assert "Invalid or expired token" in exc_info.value.detail

    def test_www_authenticate_header_set(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            decode_token("garbage")
        assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"


# ---------------------------------------------------------------------------
# CurrentUser — has_role / require_role
# ---------------------------------------------------------------------------


class TestCurrentUser:
    def test_user_id_stored(self) -> None:
        u = CurrentUser("alice", Role.admin)
        assert u.user_id == "alice"

    def test_role_stored(self) -> None:
        u = CurrentUser("alice", Role.reviewer)
        assert u.role == Role.reviewer

    # --- has_role hierarchy ---

    def test_admin_has_admin_role(self) -> None:
        assert CurrentUser("u", Role.admin).has_role(Role.admin) is True

    def test_admin_has_reviewer_role(self) -> None:
        assert CurrentUser("u", Role.admin).has_role(Role.reviewer) is True

    def test_admin_has_executor_role(self) -> None:
        assert CurrentUser("u", Role.admin).has_role(Role.executor) is True

    def test_reviewer_does_not_have_admin_role(self) -> None:
        assert CurrentUser("u", Role.reviewer).has_role(Role.admin) is False

    def test_reviewer_has_reviewer_role(self) -> None:
        assert CurrentUser("u", Role.reviewer).has_role(Role.reviewer) is True

    def test_reviewer_has_executor_role(self) -> None:
        assert CurrentUser("u", Role.reviewer).has_role(Role.executor) is True

    def test_executor_does_not_have_admin_role(self) -> None:
        assert CurrentUser("u", Role.executor).has_role(Role.admin) is False

    def test_executor_does_not_have_reviewer_role(self) -> None:
        assert CurrentUser("u", Role.executor).has_role(Role.reviewer) is False

    def test_executor_has_executor_role(self) -> None:
        assert CurrentUser("u", Role.executor).has_role(Role.executor) is True

    # --- require_role ---

    def test_require_role_passes_for_sufficient_role(self) -> None:
        u = CurrentUser("u", Role.admin)
        u.require_role(Role.reviewer)  # should not raise

    def test_require_role_raises_403_for_insufficient_role(self) -> None:
        u = CurrentUser("u", Role.executor)
        with pytest.raises(HTTPException) as exc_info:
            u.require_role(Role.admin)
        assert exc_info.value.status_code == 403

    def test_require_role_detail_contains_required_role(self) -> None:
        u = CurrentUser("u", Role.executor)
        with pytest.raises(HTTPException) as exc_info:
            u.require_role(Role.reviewer)
        assert "reviewer" in exc_info.value.detail

    def test_require_role_exact_match_passes(self) -> None:
        u = CurrentUser("u", Role.reviewer)
        u.require_role(Role.reviewer)  # should not raise


class TestRoleRankConstants:
    """Verify the _ROLE_RANK mapping encodes the intended hierarchy."""

    def test_admin_rank_highest(self) -> None:
        assert _ROLE_RANK[Role.admin] > _ROLE_RANK[Role.reviewer]

    def test_reviewer_rank_above_executor(self) -> None:
        assert _ROLE_RANK[Role.reviewer] > _ROLE_RANK[Role.executor]

    def test_executor_rank_lowest(self) -> None:
        assert _ROLE_RANK[Role.executor] == 0


# ---------------------------------------------------------------------------
# get_current_user (async dependency)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_auth_disabled_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    result = await get_current_user(token=None)
    assert result is None


@pytest.mark.asyncio
async def test_get_current_user_auth_disabled_ignores_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    # Even if a token is passed, when auth is disabled it should be ignored.
    result = await get_current_user(token="some-token")
    assert result is None


@pytest.mark.asyncio
async def test_get_current_user_auth_enabled_no_token_raises_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_auth_enabled_empty_token_raises_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    # OAuth2PasswordBearer passes None for missing token; empty string is falsy.
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_auth_enabled_valid_token_returns_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    jwt_str = create_access_token("bob", "reviewer")
    user = await get_current_user(token=jwt_str)
    assert user is not None
    assert user.user_id == "bob"
    assert user.role == Role.reviewer


@pytest.mark.asyncio
async def test_get_current_user_auth_enabled_admin_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    jwt_str = create_access_token("carol", "admin")
    user = await get_current_user(token=jwt_str)
    assert user is not None
    assert user.role == Role.admin


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_raises_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="not-a-real-token")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_missing_role_defaults_to_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a token's payload lacks a 'role' key, executor is the default."""
    import json as _json

    monkeypatch.setenv("AUTH_ENABLED", "true")
    # Build a token with no 'role' field.
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {"sub": "norole", "exp": future.timestamp()}
    raw = _json.dumps(payload).encode()
    token = "mock." + _base64.b64encode(raw).decode()
    user = await get_current_user(token=token)
    assert user is not None
    # payload.get("role", Role.executor) — should fall back to Role.executor
    assert user.role == Role.executor


# ---------------------------------------------------------------------------
# require_admin / require_reviewer / require_executor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_admin_passes_when_user_is_none() -> None:
    """When auth is disabled (user=None), all require_* pass through."""
    result = await require_admin(user=None)
    assert result is None


@pytest.mark.asyncio
async def test_require_admin_passes_for_admin_user() -> None:
    user = CurrentUser("u", Role.admin)
    result = await require_admin(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_admin_raises_403_for_reviewer() -> None:
    user = CurrentUser("u", Role.reviewer)
    with pytest.raises(HTTPException) as exc_info:
        await require_admin(user=user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_admin_raises_403_for_executor() -> None:
    user = CurrentUser("u", Role.executor)
    with pytest.raises(HTTPException) as exc_info:
        await require_admin(user=user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_reviewer_passes_for_reviewer() -> None:
    user = CurrentUser("u", Role.reviewer)
    result = await require_reviewer(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_reviewer_passes_for_admin() -> None:
    user = CurrentUser("u", Role.admin)
    result = await require_reviewer(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_reviewer_raises_403_for_executor() -> None:
    user = CurrentUser("u", Role.executor)
    with pytest.raises(HTTPException) as exc_info:
        await require_reviewer(user=user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_executor_passes_for_executor() -> None:
    user = CurrentUser("u", Role.executor)
    result = await require_executor(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_executor_passes_for_admin() -> None:
    user = CurrentUser("u", Role.admin)
    result = await require_executor(user=user)
    assert result is user


@pytest.mark.asyncio
async def test_require_executor_passes_when_none() -> None:
    result = await require_executor(user=None)
    assert result is None
