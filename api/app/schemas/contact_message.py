from pydantic import BaseModel, EmailStr, Field, model_validator


class ContactMessageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    # Both optional individually, but at least one of the two is required — see
    # _require_email_or_phone below. A visitor needs to be reachable somehow, but not necessarily
    # both ways.
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    message: str = Field(min_length=50)
    # Only required (and only checked) for an anonymous submitter — see routers/contact.py's
    # create_contact_message. A logged-in submitter is already a known, authenticated account, so
    # asking them to also solve a CAPTCHA would be redundant friction.
    turnstile_token: str | None = None

    @model_validator(mode="after")
    def _require_email_or_phone(self) -> "ContactMessageCreate":
        if not self.email and not (self.phone or "").strip():
            raise ValueError("Provide at least an email address or a phone number")
        return self
