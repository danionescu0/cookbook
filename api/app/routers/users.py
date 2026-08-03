import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import AuthUser, get_current_user
from app.database import get_db
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
