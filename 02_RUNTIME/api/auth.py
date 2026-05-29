"""JWT-based authentication and RBAC for Chromatic Harness v2.

Enabled when AUTH_ENABLED=true (default: disabled for backward compatibility).
Roles: admin > reviewer > executor.
"""

import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

try:
    from jose import JWTError, jwt

    _JOSE_AVAILABLE = True
except ImportError:
    _JOSE_AVAILABLE = False

try:
    import bcrypt as _bcrypt

    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False

_DEPS_AVAILABLE = _JOSE_AVAILABLE and _BCRYPT_AVAILABLE

AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() == "true"
SECRET_KEY = os.environ.get("AUTH_SECRET_KEY", "chromatic-dev-secret-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("AUTH_TOKEN_EXPIRE_MINUTES", "60"))
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


class Role(str, Enum):
    admin = "admin"
    reviewer = "reviewer"
    executor = "executor"


# Role hierarchy — higher index = more permissive
_ROLE_RANK = {Role.executor: 0, Role.reviewer: 1, Role.admin: 2}


def hash_password(plain: str) -> str:
    if not _BCRYPT_AVAILABLE:
        raise RuntimeError("bcrypt not installed")
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if not _BCRYPT_AVAILABLE:
        return False
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    if not _DEPS_AVAILABLE:
        raise RuntimeError("python-jose not installed")
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    if not _DEPS_AVAILABLE:
        raise RuntimeError("python-jose not installed")
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


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
    token: Optional[str] = Depends(_oauth2_scheme),
) -> Optional[CurrentUser]:
    """FastAPI dependency. Returns None when auth is disabled (open access)."""
    if not AUTH_ENABLED:
        return None
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    return CurrentUser(
        user_id=payload["sub"],
        role=Role(payload.get("role", Role.executor)),
    )


async def require_admin(
    user: Optional[CurrentUser] = Depends(get_current_user),
) -> Optional[CurrentUser]:
    if user is not None:
        user.require_role(Role.admin)
    return user


async def require_reviewer(
    user: Optional[CurrentUser] = Depends(get_current_user),
) -> Optional[CurrentUser]:
    if user is not None:
        user.require_role(Role.reviewer)
    return user


async def require_executor(
    user: Optional[CurrentUser] = Depends(get_current_user),
) -> Optional[CurrentUser]:
    if user is not None:
        user.require_role(Role.executor)
    return user
