"""JWT-based authentication and RBAC for Chromatic Harness v2.

Authentication is enabled unless AUTH_ENABLED is explicitly disabled.
Roles: admin > reviewer > executor.
"""

import os
import secrets  # pragma: allowlist secret
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer  # pragma: allowlist secret

try:
    import jwt
    from jwt import InvalidTokenError

    _JWT_AVAILABLE = True
except ImportError:
    _JWT_AVAILABLE = False

try:
    import bcrypt as _bcrypt

    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False

_DEPS_AVAILABLE = _JWT_AVAILABLE and _BCRYPT_AVAILABLE
_MIN_SECRET_BYTES = 32

_DEV_FALLBACK_SECRET = secrets.token_urlsafe(32)  # pragma: allowlist secret


def is_production() -> bool:
    """Return True when the runtime is explicitly configured for production."""
    return os.environ.get("APP_ENV", "development").lower() == "production"


def _configured_secret() -> Optional[str]:  # pragma: allowlist secret
    return os.environ.get("AUTH_SECRET_KEY")  # pragma: allowlist secret


def _require_secure_secret() -> None:  # pragma: allowlist secret
    """Fail loudly if production mode has no configured signing secret."""  # pragma: allowlist secret
    configured = _configured_secret()
    if is_production() and (not configured or len(configured.encode("utf-8")) < _MIN_SECRET_BYTES):
        raise RuntimeError(
            "AUTH_SECRET_KEY must be set to a cryptographically secure value of at least 32 bytes in production."
        )  # pragma: allowlist secret


# Eager safety check on import so production cannot start with the default secret.
_require_secure_secret()


def is_auth_enabled() -> bool:
    """Read AUTH_ENABLED at call time so test import order cannot stale-cache it."""
    return os.environ.get("AUTH_ENABLED", "true").lower() == "true"


SECRET_KEY = _configured_secret() or _DEV_FALLBACK_SECRET  # pragma: allowlist secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("AUTH_TOKEN_EXPIRE_MINUTES", "60"))
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)  # pragma: allowlist secret


class Role(str, Enum):
    admin = "admin"
    reviewer = "reviewer"
    executor = "executor"


# Role hierarchy — higher index = more permissive
_ROLE_RANK = {Role.executor: 0, Role.reviewer: 1, Role.admin: 2}


def hash_password(plain: str) -> str:  # pragma: allowlist secret
    if not _BCRYPT_AVAILABLE:
        raise RuntimeError("bcrypt not installed")
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:  # pragma: allowlist secret
    if not _BCRYPT_AVAILABLE:
        return False
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    if not _DEPS_AVAILABLE:
        raise RuntimeError("PyJWT not installed")
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire},
        SECRET_KEY,  # pragma: allowlist secret
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:  # pragma: allowlist secret
    if not _DEPS_AVAILABLE:
        raise RuntimeError("PyJWT not installed")
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # pragma: allowlist secret
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},  # pragma: allowlist secret
        ) from exc


def _user_from_payload(payload: dict) -> "CurrentUser":
    try:
        user_id = payload["sub"]
        role = Role(payload.get("role", Role.executor))
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("missing subject")
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},  # pragma: allowlist secret
        ) from exc
    return CurrentUser(user_id=user_id, role=role)


class CurrentUser:
    def __init__(self, user_id: str, role: Role):
        self.user_id = user_id
        self.role = role

    def has_role(self, required: Role) -> bool:
        return _ROLE_RANK[self.role] >= _ROLE_RANK[required]

    def require_role(self, required: Role) -> None:
        if not self.has_role(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {required.value}",
            )


async def get_current_user(
    token: Optional[str] = Depends(_oauth2_scheme),  # pragma: allowlist secret
) -> Optional[CurrentUser]:
    """FastAPI dependency. Returns None when auth is disabled (open access)."""
    if not is_auth_enabled():
        return None
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},  # pragma: allowlist secret
        )
    return _user_from_payload(decode_token(token))


async def require_current_user(
    token: Optional[str] = Depends(_oauth2_scheme),  # pragma: allowlist secret
) -> CurrentUser:
    """FastAPI dependency that always returns a user.

    In development mode with auth disabled this returns a privileged sentinel so
    routes stay usable without a real token. In production (or when auth is enabled)
    a valid token is required.
    """
    if not is_auth_enabled() and not is_production():
        return CurrentUser(user_id="dev", role=Role.admin)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},  # pragma: allowlist secret
        )
    return _user_from_payload(decode_token(token))


async def require_admin(
    user: CurrentUser = Depends(require_current_user),
) -> CurrentUser:
    user.require_role(Role.admin)
    return user


async def require_reviewer(
    user: CurrentUser = Depends(require_current_user),
) -> CurrentUser:
    user.require_role(Role.reviewer)
    return user


async def require_executor(
    user: CurrentUser = Depends(require_current_user),
) -> CurrentUser:
    user.require_role(Role.executor)
    return user
