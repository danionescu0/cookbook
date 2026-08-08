from pydantic import BaseModel

from app.schemas.import_job import ImportJobRead


class BookmarkLinkRead(BaseModel):
    title: str
    url: str
    # True when this URL is already a Recipe this user owns, or already sitting in their import
    # queue — surfaced so the frontend can show it as non-selectable instead of letting the user
    # burn a quota slot on POST /imports/bookmark only to have it silently skipped there.
    already_imported: bool


class BookmarkParseResponse(BaseModel):
    links: list[BookmarkLinkRead]
    # None for an admin (unexempt — see routers/imports.py's _ensure_import_limit_not_reached).
    # For a non-admin, max(0, max_imports_per_user - imported_recipes_count) — how many more of
    # the links above they're allowed to select.
    remaining_quota: int | None


class BookmarkImportRequest(BaseModel):
    urls: list[str]


class BookmarkImportResult(BaseModel):
    created: list[ImportJobRead]
    # URLs from the request that were already a Recipe/ImportJob for this user — skipped rather
    # than erroring the whole batch, same "duplicate, not a failure" spirit as the single-URL
    # POST /imports's 409 today (which the bookmark bulk flow deliberately doesn't reuse, since
    # one already-imported link in a batch of twenty shouldn't reject the other nineteen).
    skipped_duplicate: list[str]
