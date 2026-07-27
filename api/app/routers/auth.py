from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import settings
from app.database import get_db
from app.settings_service import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    # admin_username stays env-only (not exposed in the Settings UI); admin_password is
    # DB-backed and editable there — see app.settings_service.
    admin_password = get_settings(db).admin_password
    if payload.username != settings.admin_username or payload.password != admin_password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return LoginResponse(access_token=create_access_token(payload.username))
