from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

ALGORITHM = "HS256"


@dataclass
class AuthUser:
    id: int
    email: str
    is_admin: bool
    is_super_admin: bool


def create_access_token(user: User) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {
        "sub": user.email,
        "user_id": user.id,
        "is_admin": user.is_admin,
        "is_super_admin": user.is_super_admin,
        "iat": issued_at,
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


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthUser:
    payload = _decode(authorization)

    # A DB round trip on every authenticated request (not just at login) — the cost of making a
    # password change actually mean something. Also doubles as the fix for a second, unrelated
    # staleness problem: is_admin/is_super_admin used to come straight from the token's own
    # claims, so demoting an admin or deleting their account had no effect until their token
    # naturally expired. Reading the row fresh here closes both gaps at once.
    user = db.get(User, payload.get("user_id"))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if user.token_valid_after is not None:
        # Missing `iat` only happens for a token minted before this column existed — treated as
        # "issued at the dawn of time" so it's invalidated by ANY password change made after
        # upgrading, rather than silently skipping the check for exactly the tokens most likely
        # to be stale.
        iat = payload.get("iat")
        issued_at = datetime.fromtimestamp(iat, tz=timezone.utc) if iat is not None else datetime.min.replace(
            tzinfo=timezone.utc
        )
        # SQLite (the test suite's stand-in for Postgres) drops tzinfo on read even for a
        # DateTime(timezone=True) column — same defensiveness as reset_password's expires_at
        # check.
        token_valid_after = user.token_valid_after
        if token_valid_after.tzinfo is None:
            token_valid_after = token_valid_after.replace(tzinfo=timezone.utc)
        if issued_at < token_valid_after:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    return AuthUser(
        id=user.id,
        email=user.email,
        is_admin=user.is_admin,
        is_super_admin=user.is_super_admin,
    )


def get_optional_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthUser | None:
    # For routes that stay reachable by anonymous visitors (public recipe browsing) but still
    # need to know who's asking, if anyone, to apply the right visibility rule. A present-but-
    # invalid/expired token is treated the same as no token at all here, not as an error — this
    # endpoint isn't the place to force a re-login.
    if not authorization:
        return None
    try:
        return get_current_user(authorization, db)
    except HTTPException:
        return None


def require_admin(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthUser:
    user = get_current_user(authorization, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def require_super_admin(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthUser:
    user = get_current_user(authorization, db)
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user
