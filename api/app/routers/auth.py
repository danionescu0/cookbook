import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.captcha import verify_turnstile
from app.database import get_db
from app.models.email_job import EmailJob, EmailJobStatus
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.queue import publish_email_job
from app.settings_service import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

_VERIFICATION_TOKEN_LIFETIME = timedelta(hours=24)
# Shorter than the verification window above — a reset link is more sensitive (it directly grants
# account access), so it's worth making a stale, forgotten link expire sooner.
_PASSWORD_RESET_TOKEN_LIFETIME = timedelta(hours=1)

# Bumped whenever the Terms and Conditions text changes materially. Kept in sync by hand with the
# frontend's copy of the same string (frontend/src/i18n/translations/{en,ro}.ts, terms.version) —
# stored per-user at signup as an audit trail of what they actually agreed to, not to gate access.
TERMS_VERSION = "2026-07-31"


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    turnstile_token: str
    terms_accepted: bool
    # The signup form's current UI language — not validated against supported_languages here
    # (falls back silently in signup() instead) since a mismatch is just a stale/unusual client,
    # not something worth failing a signup over.
    language: str | None = None


class UserRead(BaseModel):
    id: int
    email: str
    is_admin: bool
    is_super_admin: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr
    turnstile_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    turnstile_token: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


def _enqueue_email_job(db: Session, user_id: int, kind: str) -> None:
    job = EmailJob(user_id=user_id, kind=kind, status=EmailJobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        publish_email_job(job.id, user_id)
    except Exception as exc:
        job.status = EmailJobStatus.FAILED
        job.error = f"failed to publish to queue: {exc}"
        db.commit()


def _resend_verification_email(db: Session, user: User) -> None:
    # A fresh token each time (old ones are simply left to expire on their own schedule rather
    # than being explicitly invalidated) — the worker's email handler always sends the newest
    # unused one, so this is what actually goes out.
    token = EmailVerificationToken(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc) + _VERIFICATION_TOKEN_LIFETIME,
    )
    db.add(token)
    db.commit()
    _enqueue_email_job(db, user.id, "verification")


@router.post("/signup", status_code=201)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    if not payload.terms_accepted:
        raise HTTPException(status_code=400, detail="You must accept the Terms and Conditions to sign up")

    app_settings = get_settings(db)
    if not verify_turnstile(payload.turnstile_token, app_settings.turnstile_secret_key):
        raise HTTPException(status_code=400, detail="CAPTCHA verification failed")

    existing_by_email = db.scalar(select(User).where(User.email == payload.email))
    if existing_by_email is not None:
        if existing_by_email.is_verified:
            raise HTTPException(status_code=400, detail="That email is already registered")
        # A real signup was already started with this email and never confirmed — recover it
        # instead of dead-ending on a duplicate-email error (and instead of silently creating a
        # second row). Doesn't touch the original password: proving you can solve a CAPTCHA
        # isn't proof you own the mailbox, only clicking the emailed link is.
        _resend_verification_email(db, existing_by_email)
        return {
            "detail": (
                "An account with this email already exists but hasn't been verified yet — "
                "we've sent a new verification link."
            )
        }

    language = (
        payload.language
        if payload.language in app_settings.supported_languages_list
        else app_settings.default_language
    )

    password_hash = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode("ascii")
    user = User(
        email=payload.email,
        password_hash=password_hash,
        is_verified=False,
        terms_accepted_at=datetime.now(timezone.utc),
        terms_version=TERMS_VERSION,
        language=language,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _resend_verification_email(db, user)

    return {"detail": "Account created. Check your email to verify it before logging in."}


@router.post("/resend-verification")
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    app_settings = get_settings(db)
    if not verify_turnstile(payload.turnstile_token, app_settings.turnstile_secret_key):
        raise HTTPException(status_code=400, detail="CAPTCHA verification failed")

    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        raise HTTPException(status_code=404, detail="No account with that email")
    if user.is_verified:
        return {"detail": "This account is already verified — you can log in."}

    _resend_verification_email(db, user)
    return {"detail": "A new verification email has been sent."}


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    token = db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token == payload.token))
    if token is None:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    if token.used_at is not None:
        raise HTTPException(status_code=400, detail="This verification link was already used")
    # SQLite (used by the test suite) drops tzinfo on round-trip even for a DateTime(timezone=True)
    # column — Postgres doesn't. Normalize defensively rather than assume a tz-aware value back.
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This verification link has expired")

    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    user.is_verified = True
    token.used_at = datetime.now(timezone.utc)
    db.commit()

    return {"detail": "Email verified — you can log in now."}


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not bcrypt.checkpw(payload.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_verified:
        raise HTTPException(
            status_code=401, detail="Account not verified yet — check your email for the verification link."
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return LoginResponse(
        access_token=create_access_token(user),
        user=UserRead(
            id=user.id, email=user.email, is_admin=user.is_admin, is_super_admin=user.is_super_admin
        ),
    )


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    app_settings = get_settings(db)
    if not verify_turnstile(payload.turnstile_token, app_settings.turnstile_secret_key):
        raise HTTPException(status_code=400, detail="CAPTCHA verification failed")

    # Always the same response whether or not the email is registered — telling a caller "no
    # account with that email" here would let anyone enumerate registered addresses one guess at
    # a time. The email itself (sent only when a user is actually found) is where any real
    # distinction shows up.
    generic_response = {"detail": "If that email has an account, we've sent a password reset link."}

    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        return generic_response

    token = PasswordResetToken(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc) + _PASSWORD_RESET_TOKEN_LIFETIME,
    )
    db.add(token)
    db.commit()
    _enqueue_email_job(db, user.id, "password_reset")

    return generic_response


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token == payload.token))
    if token is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    if token.used_at is not None:
        raise HTTPException(status_code=400, detail="This reset link was already used")
    # Same SQLite-vs-Postgres tzinfo defensiveness as verify_email above.
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This reset link has expired")

    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user.password_hash = bcrypt.hashpw(payload.new_password.encode(), bcrypt.gensalt()).decode("ascii")
    token.used_at = datetime.now(timezone.utc)
    db.commit()

    return {"detail": "Password reset — you can log in now."}
