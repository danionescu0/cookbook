import json
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.models import ContactMessage, ContactMessageStatus
from app.settings_service import SettingsSnapshot, get_settings

logger = logging.getLogger(__name__)


def _send_contact_email(message: ContactMessage, recipient: str, app_settings: SettingsSnapshot) -> None:
    lines = [f"Name: {message.name}"]
    if message.email:
        lines.append(f"Email: {message.email}")
    if message.phone:
        lines.append(f"Phone: {message.phone}")
    lines.append("")
    lines.append(message.message)

    email_message = EmailMessage()
    email_message["Subject"] = f"New contact form message from {message.name}"
    email_message["From"] = app_settings.smtp_from_address
    email_message["To"] = recipient
    # Deliberately no Reply-To pointing at the visitor's address: live-tested against this
    # deployment's real SMTP provider (Yahoo Mail) and confirmed it silently rejects the whole
    # send with "550 Mailbox unavailable" the moment Reply-To doesn't match the authenticated
    # From/login address — reproduced even with another @yahoo.com address, so it's not a
    # domain-mismatch thing specifically, just an anti-spoofing policy on outbound Reply-To in
    # general. The visitor's email is already the first line of the body, so replying is still a
    # one-line copy-paste away — reliable delivery matters more than that one click saved.
    email_message.set_content("\n".join(lines))
    with smtplib.SMTP(app_settings.smtp_host, app_settings.smtp_port, timeout=15) as smtp:
        if app_settings.smtp_use_tls:
            smtp.starttls()
        if app_settings.smtp_username:
            smtp.login(app_settings.smtp_username, app_settings.smtp_password)
        smtp.send_message(email_message)


def handle_contact_message_job(body: bytes, db: Session) -> None:
    payload = json.loads(body)
    job_id = payload["job_id"]
    message = db.get(ContactMessage, job_id)
    if message is None:
        logger.warning("contact message %s not found, skipping", job_id)
        return

    app_settings = get_settings(db)
    if not app_settings.contact_recipient_email:
        # Not an exceptional/crash case — just an admin who hasn't set the recipient address in
        # Settings yet. Failing cleanly here (rather than raising, which would still work but log
        # as unexpected) keeps the eventual fix obvious: set contact_recipient_email.
        message.status = ContactMessageStatus.FAILED
        message.error = "no contact_recipient_email configured in Settings"
        db.commit()
        return

    message.status = ContactMessageStatus.PROCESSING
    db.commit()

    try:
        _send_contact_email(message, app_settings.contact_recipient_email, app_settings)
        message.status = ContactMessageStatus.DONE
        db.commit()
    except Exception as exc:
        db.rollback()
        message.status = ContactMessageStatus.FAILED
        message.error = str(exc)
        db.commit()
