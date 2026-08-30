from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import AuthUser, get_current_user, require_admin
from app.bookmark_parser import parse_bookmark_links
from app.database import get_db
from app.models.import_job import ImportErrorKind, ImportJob, ImportJobStatus, ImportJobType
from app.models.recipe import Recipe
from app.models.user import User
from app.queue import publish_import_job
from app.schemas.bookmark import (
    BookmarkImportRequest,
    BookmarkImportResult,
    BookmarkLinkRead,
    BookmarkParseResponse,
)
from app.schemas.import_job import ImportJobCreate, ImportJobRead
from app.settings_service import get_settings
from app.url_normalize import INSTAGRAM_HOSTS, normalize_source_url

# Any logged-in user can import for themselves (imports are always private to whoever ran them —
# see routers/recipes.py's visibility rule) — gated per-route below, not at the router level.
router = APIRouter(prefix="/imports", tags=["imports"])

_APPROVABLE_STATUSES = {ImportJobStatus.PENDING, ImportJobStatus.FAILED}


def _detect_job_type(source: str) -> ImportJobType:
    # Instagram posts need a different fetch path entirely (headless-browser rendering rather
    # than a plain HTML GET — see worker/app/instagram_client.py) since Instagram serves mostly
    # client-side-rendered content. Detected here, once, at creation time so the rest of the
    # pipeline (approval, queueing, the worker's dispatch) just branches on job.type. Called with
    # an already-normalized source (see normalize_source_url) — host detection is unaffected
    # either way, but keeping to one canonical form end to end avoids two sources of truth.
    host = (urlparse(source).hostname or "").lower()
    return ImportJobType.INSTAGRAM if host in INSTAGRAM_HOSTS else ImportJobType.SINGLE


def _get_or_404(db: Session, job_id: int) -> ImportJob:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job


def _get_owned_or_404(db: Session, job_id: int, current_user: AuthUser) -> ImportJob:
    job = _get_or_404(db, job_id)
    if not current_user.is_admin and job.created_by_user_id != current_user.id:
        # 404, not 403 — same reasoning as recipes.py: don't confirm someone else's private job
        # even exists.
        raise HTTPException(status_code=404, detail="Import job not found")
    return job


def _ensure_source_not_already_imported(db: Session, source: str, owner_id: int) -> None:
    # Scoped to this user, not global — imports are private per owner now, so two different
    # users importing the same public URL each get their own private copy; that's not a
    # duplicate. Exact string match against `source`, which the caller has already run through
    # normalize_source_url — for most sites that's still just "pasted the same link twice", but
    # for Instagram it also catches a re-shared/re-copied link to a reel already imported (see
    # README Design Decisions, "Instagram URL normalization").
    if (
        db.scalar(
            select(Recipe).where(Recipe.source_url == source, Recipe.owner_user_id == owner_id)
        )
        is not None
    ):
        raise HTTPException(status_code=409, detail="This URL has already been imported.")
    if (
        db.scalar(
            select(ImportJob).where(
                ImportJob.source == source, ImportJob.created_by_user_id == owner_id
            )
        )
        is not None
    ):
        raise HTTPException(status_code=409, detail="This URL is already in the import queue.")


def _ensure_import_limit_not_reached(db: Session, user: User) -> None:
    # Admins aren't capped — this is a monetization lever aimed at end users, not the site's own
    # curators. `imported_recipes_count` is a lifetime counter (see users.py's model docstring),
    # incremented once by the worker per successful import and never decremented — deleting a
    # recipe (or its import_jobs row) never frees up quota.
    if user.is_admin:
        return
    limit = get_settings(db).max_imports_per_user
    if user.imported_recipes_count >= limit:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Import limit reached: {user.imported_recipes_count}/{limit} recipes ever "
                "imported. Deleting a recipe does not free up quota."
            ),
        )


def _remaining_quota(db: Session, user: User) -> int | None:
    # None means unlimited (admin) — mirrors _ensure_import_limit_not_reached's own admin
    # exemption. Used by the bookmark endpoints below to tell the frontend how many more links a
    # non-admin may select, and to enforce that same number server-side on the actual import.
    if user.is_admin:
        return None
    limit = get_settings(db).max_imports_per_user
    return max(0, limit - user.imported_recipes_count)


def _already_imported_urls(db: Session, urls: list[str], owner_id: int) -> set[str]:
    # Single bulk query per table rather than one _ensure_source_not_already_imported() call per
    # URL — a bookmark file can carry dozens of links, and this only ever runs against this one
    # user's own rows (recipes/import_jobs are both private-per-owner, see the module docstring).
    # Returns a subset of the *raw* input `urls` (matching what the caller passed in, e.g. for a
    # per-link `already_imported` flag) — the comparison itself is done on normalized values,
    # since stored source/source_url rows are normalized (see normalize_source_url) but the raw
    # input here may not be (a bookmark file's links are never normalized before this call).
    if not urls:
        return set()
    normalized_by_raw = {url: normalize_source_url(url) for url in urls}
    normalized_values = set(normalized_by_raw.values())
    from_recipes = db.scalars(
        select(Recipe.source_url).where(
            Recipe.source_url.in_(normalized_values), Recipe.owner_user_id == owner_id
        )
    )
    from_jobs = db.scalars(
        select(ImportJob.source).where(
            ImportJob.source.in_(normalized_values), ImportJob.created_by_user_id == owner_id
        )
    )
    already_normalized = {url for url in from_recipes if url is not None} | set(from_jobs)
    return {raw for raw, normalized in normalized_by_raw.items() if normalized in already_normalized}


def _queue_and_publish(db: Session, job: ImportJob) -> None:
    # Commit `queued` *before* publishing, not after: publishing first meant a worker fast
    # enough to consume the message before this transaction committed would read the job's
    # still-stale prior status. Committing first guarantees the queued status is visible to
    # any consumer before the message can possibly reach one.
    job.status = ImportJobStatus.QUEUED
    job.error = None
    job.error_kind = None
    db.commit()
    db.refresh(job)

    try:
        publish_import_job(job.id, job.type.value, job.source)
    except Exception as exc:
        job.status = ImportJobStatus.FAILED
        job.error = f"failed to publish to queue: {exc}"
        job.error_kind = ImportErrorKind.TECHNICAL
        db.commit()
        db.refresh(job)


def _serialize(job: ImportJob, current_user: AuthUser) -> ImportJobRead:
    # A non-admin never sees the raw technical `error` text — only the categorized error_kind,
    # which the frontend maps to a friendly canned message. Admins (and the admin-only
    # failed-imports page) get the full thing.
    return ImportJobRead(
        id=job.id,
        category_id=job.category_id,
        type=job.type,
        source=job.source,
        status=job.status,
        error=job.error if current_user.is_admin else None,
        error_kind=job.error_kind,
        created_at=job.created_at,
        created_by_user_id=job.created_by_user_id,
        created_by_email=job.created_by_email if current_user.is_admin else None,
        dismissed_at=job.dismissed_at,
        admin_reviewed_at=job.admin_reviewed_at,
    )


@router.get("", response_model=list[ImportJobRead])
def list_import_jobs(
    response: Response,
    status: ImportJobStatus | None = Query(default=None),
    # Only meaningful alongside status=failed — lets the admin failed-imports page exclude jobs
    # it's already marked reviewed (see POST /imports/{id}/mark-reviewed) without ever touching
    # dismissed_at, which stays exclusively the owner's own signal.
    admin_reviewed: bool | None = Query(default=None),
    # Both optional and unused by ImportManager's existing calls, which keep getting the full,
    # unpaginated list exactly as before — only the admin failed-imports page passes these.
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> list[ImportJobRead]:
    stmt = select(ImportJob).order_by(ImportJob.created_at.desc())
    count_stmt = select(func.count()).select_from(ImportJob)
    if not current_user.is_admin:
        stmt = stmt.where(ImportJob.created_by_user_id == current_user.id)
        count_stmt = count_stmt.where(ImportJob.created_by_user_id == current_user.id)
    if status is not None:
        stmt = stmt.where(ImportJob.status == status)
        count_stmt = count_stmt.where(ImportJob.status == status)
    if admin_reviewed is not None:
        clause = (
            ImportJob.admin_reviewed_at.is_not(None)
            if admin_reviewed
            else ImportJob.admin_reviewed_at.is_(None)
        )
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)

    if limit is not None:
        response.headers["X-Total-Count"] = str(db.scalar(count_stmt) or 0)
        stmt = stmt.offset(offset).limit(limit)

    jobs = list(db.scalars(stmt))
    return [_serialize(job, current_user) for job in jobs]


@router.post("", response_model=ImportJobRead, status_code=201)
def create_import_job(
    payload: ImportJobCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> ImportJobRead:
    user = db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_import_limit_not_reached(db, user)
    source = normalize_source_url(payload.source)
    _ensure_source_not_already_imported(db, source, current_user.id)

    # category_id starts null — the worker resolves it from Claude's own suggestion once
    # extraction succeeds (see worker/app/handlers.py's _resolve_category_id), rather than the
    # requester picking one up front.
    job = ImportJob(
        source=source,
        type=_detect_job_type(source),
        created_by_user_id=current_user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if not current_user.is_admin:
        # A regular user's import is always private to them — no public-exposure review is
        # needed, so it queues immediately instead of waiting on an admin's approval click. An
        # admin's own job keeps the existing pending -> approve step.
        _queue_and_publish(db, job)

    return _serialize(job, current_user)


@router.post("/bookmark/parse", response_model=BookmarkParseResponse)
def parse_bookmark_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> BookmarkParseResponse:
    # Read-only: no ImportJob rows are created here. The user picks which of these to actually
    # import in a second step (POST /imports/bookmark) — see README Design Decisions, "Bookmark
    # import".
    content = file.file.read()
    try:
        html = content.decode("utf-8")
    except UnicodeDecodeError:
        html = content.decode("latin-1")
    links = parse_bookmark_links(html)

    user = db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    already_imported = _already_imported_urls(db, [link.url for link in links], current_user.id)

    return BookmarkParseResponse(
        links=[
            BookmarkLinkRead(
                title=link.title, url=link.url, already_imported=link.url in already_imported
            )
            for link in links
        ],
        remaining_quota=_remaining_quota(db, user),
    )


@router.post("/bookmark", response_model=BookmarkImportResult)
def import_bookmark_selection(
    payload: BookmarkImportRequest,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> BookmarkImportResult:
    user = db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # De-duplicated first so the quota check below counts only genuinely new imports — a link
    # that's already a Recipe/ImportJob of this user's shouldn't cost them a slot of their
    # remaining quota just because it happened to be selected again.
    requested = list(dict.fromkeys(payload.urls))  # de-dupe within the request, preserve order
    already_imported = _already_imported_urls(db, requested, current_user.id)
    not_yet_imported = [url for url in requested if url not in already_imported]

    # A second dedup pass, this time by *normalized* value: two raw URLs in the same batch can be
    # different Instagram share links to the same reel (see normalize_source_url) — without this,
    # selecting both would create two jobs for identical content in one request, the same bug
    # this whole normalization effort exists to close.
    seen_normalized: set[str] = set()
    to_create: list[str] = []
    duplicate_within_batch: list[str] = []
    for url in not_yet_imported:
        normalized = normalize_source_url(url)
        if normalized in seen_normalized:
            duplicate_within_batch.append(url)
        else:
            seen_normalized.add(normalized)
            to_create.append(url)

    remaining = _remaining_quota(db, user)
    if remaining is not None and len(to_create) > remaining:
        raise HTTPException(
            status_code=400,
            detail=(
                f"You selected {len(to_create)} new recipes to import, but only {remaining} "
                "of your import quota remain. Deleting a recipe does not free up quota."
            ),
        )

    created: list[ImportJob] = []
    for url in to_create:
        job = ImportJob(
            source=normalize_source_url(url), type=ImportJobType.BOOKMARK, created_by_user_id=current_user.id
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        if not current_user.is_admin:
            # Same immediate-queue behavior as a regular single-URL import for a non-admin (see
            # create_import_job) — an admin's own bookmark-derived jobs stay `pending`, requiring
            # the same explicit approval click as any other admin-created import.
            _queue_and_publish(db, job)
        created.append(job)

    return BookmarkImportResult(
        created=[_serialize(job, current_user) for job in created],
        skipped_duplicate=[url for url in requested if url in already_imported] + duplicate_within_batch,
    )


@router.post("/{job_id}/approve", response_model=ImportJobRead)
def approve_import_job(
    job_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> ImportJobRead:
    # Also doubles as "retry": a `failed` job (e.g. RabbitMQ was down) can be approved again — by
    # an admin, or by whoever created it.
    job = _get_owned_or_404(db, job_id, current_user)
    if job.status not in _APPROVABLE_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Cannot approve a job in status {job.status.value}"
        )
    _queue_and_publish(db, job)
    return _serialize(job, current_user)


@router.get("/{job_id}", response_model=ImportJobRead)
def get_import_job(
    job_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> ImportJobRead:
    job = _get_owned_or_404(db, job_id, current_user)
    return _serialize(job, current_user)


@router.post("/{job_id}/dismiss", response_model=ImportJobRead)
def dismiss_import_job(
    job_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> ImportJobRead:
    # Clears the failed-import card from the owner's account page (see frontend's
    # PendingImportsPanel) — never touches the admin failed-imports page, which ignores
    # dismissed_at entirely so an owner dismissing their own notification can't erase the record.
    job = _get_owned_or_404(db, job_id, current_user)
    if job.status != ImportJobStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only a failed import can be dismissed")
    job.dismissed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return _serialize(job, current_user)


@router.post("/{job_id}/mark-reviewed", response_model=ImportJobRead, dependencies=[Depends(require_admin)])
def mark_import_reviewed(
    job_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> ImportJobRead:
    # An admin's own "I've looked at this" signal on the Failed Imports back office page —
    # deliberately a separate column from the owner's dismissed_at (see ImportJob.admin_reviewed_at):
    # neither actor's action can silently clear the other's. Admin-only, and not scoped to jobs
    # this admin created — the whole point is triaging every user's failures.
    job = _get_or_404(db, job_id)
    if job.status != ImportJobStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only a failed import can be marked reviewed")
    job.admin_reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return _serialize(job, current_user)


@router.delete("/{job_id}", status_code=204)
def delete_import_job(
    job_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> None:
    job = _get_owned_or_404(db, job_id, current_user)
    db.delete(job)
    db.commit()
