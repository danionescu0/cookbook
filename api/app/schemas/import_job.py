from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.import_job import ImportErrorKind, ImportJobStatus, ImportJobType


class ImportJobCreate(BaseModel):
    source: str
    category_id: int


class ImportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    type: ImportJobType
    source: str
    status: ImportJobStatus
    # Raw technical text — nulled out for a non-admin caller (see routers/imports.py's
    # _serialize); error_kind below is what a non-admin actually renders.
    error: str | None
    error_kind: ImportErrorKind | None = None
    created_at: datetime
    created_by_username: str | None = None
    # Set once the owner dismisses a failed job from their account page — see
    # POST /imports/{id}/dismiss. Never consulted by the admin failed-imports page.
    dismissed_at: datetime | None = None
    # Set once an admin marks a failed job as handled on the Failed Imports back office page — see
    # POST /imports/{id}/mark-reviewed. Independent of dismissed_at above; never touched by the
    # owner's own dismiss action.
    admin_reviewed_at: datetime | None = None
