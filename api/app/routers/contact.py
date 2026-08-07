from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import AuthUser, get_optional_current_user
from app.captcha import verify_turnstile
from app.database import get_db
from app.models.contact_message import ContactMessage, ContactMessageStatus
from app.queue import publish_contact_message_job
from app.schemas.contact_message import ContactMessageCreate
from app.settings_service import get_settings

# Reachable both logged in and logged out — see get_optional_current_user. A logged-in submitter
# skips the CAPTCHA entirely (already an authenticated account); an anonymous one must solve one.
router = APIRouter(prefix="/contact", tags=["contact"])


@router.post("", status_code=201)
def create_contact_message(
    payload: ContactMessageCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser | None = Depends(get_optional_current_user),
) -> dict[str, int]:
    if current_user is None:
        app_settings = get_settings(db)
        if not payload.turnstile_token or not verify_turnstile(
            payload.turnstile_token, app_settings.turnstile_secret_key
        ):
            raise HTTPException(status_code=400, detail="CAPTCHA verification failed")

    message = ContactMessage(
        name=payload.name.strip(),
        email=payload.email,
        phone=(payload.phone or "").strip() or None,
        message=payload.message,
        submitted_by_user_id=current_user.id if current_user else None,
        status=ContactMessageStatus.QUEUED,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    try:
        publish_contact_message_job(message.id)
    except Exception as exc:
        # Matches every other job type's pattern (see routers/imports.py's _queue_and_publish):
        # the submission itself already succeeded and is durably recorded — a broken queue
        # publish must not turn that into a user-facing error, just a job that stays failed and
        # never gets picked up (no retry UI for this one, since there's no admin viewer page).
        message.status = ContactMessageStatus.FAILED
        message.error = f"failed to publish to queue: {exc}"
        db.commit()

    return {"id": message.id}
