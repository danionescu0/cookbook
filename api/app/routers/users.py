from datetime import datetime

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import AuthUser, get_current_user, require_super_admin
from app.database import get_db
from app.models.recipe import Recipe
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


class UserProfile(BaseModel):
    id: int
    username: str
    email: str | None
    is_admin: bool
    is_super_admin: bool
    # Lifetime count of successful imports — see users.imported_recipes_count. Meaningless for
    # admins (they're exempt from the cap), but returned for everyone for a uniform response
    # shape; the frontend only shows/enforces it for non-admins.
    imported_recipes_count: int


class UserAdminRead(BaseModel):
    id: int
    username: str
    email: str | None
    is_verified: bool
    created_at: datetime
    # Null if the account has never logged in since this column existed — see
    # users.last_login_at.
    last_login_at: datetime | None
    # Lifetime count, not "currently owns" — see users.imported_recipes_count.
    imported_recipes_count: int
    owned_recipes_count: int
    shared_recipes_count: int


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/me", response_model=UserProfile)
def read_profile(
    db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> UserProfile:
    user = _get_user_or_404(db, current_user.id)
    return UserProfile(
        id=user.id,
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
        is_super_admin=user.is_super_admin,
        imported_recipes_count=user.imported_recipes_count,
    )


@router.get("", response_model=list[UserAdminRead], dependencies=[Depends(require_super_admin)])
def list_users(db: Session = Depends(get_db)) -> list[UserAdminRead]:
    # Two correlated scalar subqueries rather than a JOIN + GROUP BY with a FILTER-clause
    # aggregate: portable across the Postgres used in production and the SQLite the test suite
    # runs against (FILTER support there depends on the SQLite version bundled with Python).
    owned_count = (
        select(func.count(Recipe.id)).where(Recipe.owner_user_id == User.id).correlate(User).scalar_subquery()
    )
    shared_count = (
        select(func.count(Recipe.id))
        .where(Recipe.owner_user_id == User.id, Recipe.is_shared.is_(True))
        .correlate(User)
        .scalar_subquery()
    )
    rows = db.execute(
        select(User, owned_count, shared_count).order_by(User.created_at.asc())
    ).all()
    return [
        UserAdminRead(
            id=user.id,
            username=user.username,
            email=user.email,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            imported_recipes_count=user.imported_recipes_count,
            owned_recipes_count=owned,
            shared_recipes_count=shared,
        )
        for user, owned, shared in rows
    ]


@router.patch("/me/password", status_code=204)
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> None:
    user = _get_user_or_404(db, current_user.id)
    if not bcrypt.checkpw(payload.current_password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    user.password_hash = bcrypt.hashpw(payload.new_password.encode(), bcrypt.gensalt()).decode("ascii")
    db.commit()
