from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.import_job import ImportErrorKind, ImportJobStatus, ImportJobType


class ImportJobCreate(BaseModel):
    source: str


class ImportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Null until the worker resolves it from Claude's own suggestion once extraction succeeds —
    # see worker/app/handlers.py's _resolve_category_id. Stays null forever for a job that never
    # gets that far (e.g. a failed fetch).
    category_id: int | None
    type: ImportJobType
    source: str
    status: ImportJobStatus
    # Raw technical text — nulled out for a non-admin caller (see routers/imports.py's
    # _serialize); error_kind below is what a non-admin actually renders.
    error: str | None
    error_kind: ImportErrorKind | None = None
    created_at: datetime
    created_by_user_id: int | None = None
    # Only populated for an admin caller — see routers/imports.py's _serialize, same nulling
    # pattern already used for `error` above and routers/recipes.py's owner_email.
    created_by_email: str | None = None
    # Set once the owner dismisses a failed job from their account page — see
    # POST /imports/{id}/dismiss. Never consulted by the admin failed-imports page.
    dismissed_at: datetime | None = None
    # Set once an admin marks a failed job as handled on the Failed Imports back office page — see
    # POST /imports/{id}/mark-reviewed. Independent of dismissed_at above; never touched by the
    # owner's own dismiss action.
    admin_reviewed_at: datetime | None = None
