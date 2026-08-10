from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

from app.config import settings
from app.models.user import User

ALGORITHM = "HS256"


@dataclass
class AuthUser:
    id: int
    email: str
    is_admin: bool
    is_super_admin: bool


def create_access_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {
        "sub": user.email,
        "user_id": user.id,
        "is_admin": user.is_admin,
        "is_super_admin": user.is_super_admin,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def _decode(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ")
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    payload = _decode(authorization)
    return AuthUser(
        id=payload["user_id"],
        email=payload["sub"],
        is_admin=bool(payload.get("is_admin")),
        is_super_admin=bool(payload.get("is_super_admin")),
    )


def get_optional_current_user(authorization: str | None = Header(default=None)) -> AuthUser | None:
    # For routes that stay reachable by anonymous visitors (public recipe browsing) but still
    # need to know who's asking, if anyone, to apply the right visibility rule. A present-but-
    # invalid/expired token is treated the same as no token at all here, not as an error — this
    # endpoint isn't the place to force a re-login.
    if not authorization:
        return None
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None


def require_admin(authorization: str | None = Header(default=None)) -> AuthUser:
    user = get_current_user(authorization)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_super_admin(authorization: str | None = Header(default=None)) -> AuthUser:
    user = get_current_user(authorization)
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user
