import json
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmailJob, EmailJobStatus, EmailVerificationToken, User
from app.settings_service import SettingsSnapshot, get_settings

logger = logging.getLogger(__name__)


def _send_verification_email(user: User, token: EmailVerificationToken, app_settings: SettingsSnapshot) -> None:
    link = f"{app_settings.public_site_url.rstrip('/')}/verify-email?token={token.token}"
    message = EmailMessage()
    message["Subject"] = "Verify your Cookbook account"
    message["From"] = app_settings.smtp_from_address
    message["To"] = user.email
    message.set_content(
        "Welcome to Cookbook!\n\n"
        f"Verify your email address by opening this link:\n\n{link}\n\n"
        "If you didn't sign up for this, you can ignore this message."
    )
    with smtplib.SMTP(app_settings.smtp_host, app_settings.smtp_port, timeout=15) as smtp:
        if app_settings.smtp_use_tls:
            smtp.starttls()
        if app_settings.smtp_username:
            smtp.login(app_settings.smtp_username, app_settings.smtp_password)
        smtp.send_message(message)


def handle_email_job(body: bytes, db: Session) -> None:
    payload = json.loads(body)
    job_id = payload["job_id"]
    job = db.get(EmailJob, job_id)
    if job is None:
        logger.warning("email job %s not found, skipping", job_id)
        return

    user = db.get(User, job.user_id)
    if user is None:
        job.status = EmailJobStatus.FAILED
        job.error = "user not found"
        db.commit()
        return
    if not user.email:
        # Shouldn't happen — only self-service signup (which always collects an email) enqueues
        # these. The migration-seeded admin has no email and never triggers this job.
        job.status = EmailJobStatus.FAILED
        job.error = "user has no email address on file"
        db.commit()
        return

    job.status = EmailJobStatus.PROCESSING
    db.commit()

    try:
        if job.kind != "verification":
            raise RuntimeError(f"unknown email job kind: {job.kind!r}")

        token = db.scalar(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None))
            .order_by(EmailVerificationToken.created_at.desc())
        )
        if token is None:
            raise RuntimeError(f"no unused verification token found for user {user.id}")

        _send_verification_email(user, token, get_settings(db))
        job.status = EmailJobStatus.DONE
        db.commit()
    except Exception as exc:
        db.rollback()
        job.status = EmailJobStatus.FAILED
        job.error = str(exc)
        db.commit()
