import json
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmailJob, EmailJobStatus, EmailVerificationToken, PasswordResetToken, User
from app.settings_service import SettingsSnapshot, get_settings

logger = logging.getLogger(__name__)

# Kept in sync by hand with the tone/content of frontend/src/i18n/translations/{en,ro}.ts's
# `landing` section — the one place in the app that already explains what the site is in a
# sentence. Only "en"/"ro" exist here regardless of how many languages `supported_languages`
# lists; _verification_email_copy falls back to "en" for anything else.
_VERIFICATION_EMAIL_COPY: dict[str, dict[str, str]] = {
    "en": {
        "subject": "Verify your Cookbook account",
        "body": (
            "Hi,\n\n"
            "Welcome to Cookbook — a cookbook that's actually yours. Every recipe here is cooked, "
            "tested, and translated by real people: browse what's already shared, import your own "
            "from a URL, or add one by hand. Recipes you add are private to you by default; you "
            "can share one with the community whenever you choose.\n\n"
            "Verify your email address by opening this link:\n\n{link}\n\n"
            "If you didn't sign up for this, you can ignore this message."
        ),
    },
    "ro": {
        "subject": "Confirmă-ți contul Cookbook",
        "body": (
            "Salut!\n\n"
            "Bine ai venit pe Cookbook — un caiet de rețete cu adevărat al tău. Fiecare rețetă de "
            "aici e gătită, testată și tradusă de oameni reali: răsfoiește ce e deja partajat, "
            "importă propriile rețete de pe un link sau adaugă-le manual. Rețetele adăugate de tine "
            "sunt private în mod implicit; poți partaja oricând una cu comunitatea.\n\n"
            "Confirmă-ți adresa de email deschizând acest link:\n\n{link}\n\n"
            "Dacă nu tu ai creat acest cont, poți ignora acest mesaj."
        ),
    },
}

# Same EN/RO-only, falls-back-to-"en" convention as _VERIFICATION_EMAIL_COPY above.
_PASSWORD_RESET_EMAIL_COPY: dict[str, dict[str, str]] = {
    "en": {
        "subject": "Reset your Cookbook password",
        "body": (
            "Hi,\n\n"
            "Someone (hopefully you) asked to reset the password for this Cookbook account. Open "
            "this link to choose a new one — it expires in 1 hour:\n\n{link}\n\n"
            "If you didn't request this, you can safely ignore this message — your password won't "
            "change unless you open the link above."
        ),
    },
    "ro": {
        "subject": "Resetează-ți parola Cookbook",
        "body": (
            "Salut!\n\n"
            "Cineva (sperăm că tu) a cerut resetarea parolei pentru acest cont Cookbook. Deschide "
            "acest link ca să alegi o parolă nouă — expiră în 1 oră:\n\n{link}\n\n"
            "Dacă nu tu ai cerut asta, poți ignora acest mesaj — parola ta nu se schimbă decât dacă "
            "deschizi linkul de mai sus."
        ),
    },
}


def _verification_email_copy(language: str) -> dict[str, str]:
    return _VERIFICATION_EMAIL_COPY.get(language, _VERIFICATION_EMAIL_COPY["en"])


def _password_reset_email_copy(language: str) -> dict[str, str]:
    return _PASSWORD_RESET_EMAIL_COPY.get(language, _PASSWORD_RESET_EMAIL_COPY["en"])


def _send_email(user: User, subject: str, body: str, app_settings: SettingsSnapshot) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = app_settings.smtp_from_address
    message["To"] = user.email
    message.set_content(body)
    with smtplib.SMTP(app_settings.smtp_host, app_settings.smtp_port, timeout=15) as smtp:
        if app_settings.smtp_use_tls:
            smtp.starttls()
        if app_settings.smtp_username:
            smtp.login(app_settings.smtp_username, app_settings.smtp_password)
        smtp.send_message(message)


def _send_verification_email(user: User, token: EmailVerificationToken, app_settings: SettingsSnapshot) -> None:
    link = f"{app_settings.public_site_url.rstrip('/')}/verify-email?token={token.token}"
    copy = _verification_email_copy(user.language)
    _send_email(user, copy["subject"], copy["body"].format(link=link), app_settings)


def _send_password_reset_email(
    user: User, token: PasswordResetToken, app_settings: SettingsSnapshot
) -> None:
    link = f"{app_settings.public_site_url.rstrip('/')}/reset-password?token={token.token}"
    copy = _password_reset_email_copy(user.language)
    _send_email(user, copy["subject"], copy["body"].format(link=link), app_settings)


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

    job.status = EmailJobStatus.PROCESSING
    db.commit()

    try:
        app_settings = get_settings(db)
        if job.kind == "verification":
            token = db.scalar(
                select(EmailVerificationToken)
                .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None))
                .order_by(EmailVerificationToken.created_at.desc())
            )
            if token is None:
                raise RuntimeError(f"no unused verification token found for user {user.id}")
            _send_verification_email(user, token, app_settings)
        elif job.kind == "password_reset":
            token = db.scalar(
                select(PasswordResetToken)
                .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
                .order_by(PasswordResetToken.created_at.desc())
            )
            if token is None:
                raise RuntimeError(f"no unused password reset token found for user {user.id}")
            _send_password_reset_email(user, token, app_settings)
        else:
            raise RuntimeError(f"unknown email job kind: {job.kind!r}")

        job.status = EmailJobStatus.DONE
        db.commit()
    except Exception as exc:
        db.rollback()
        job.status = EmailJobStatus.FAILED
        job.error = str(exc)
        db.commit()
