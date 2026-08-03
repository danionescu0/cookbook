from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AuthUser, get_current_user
from app.database import get_db
from app.models.category import Category
from app.models.import_job import ImportJob, ImportJobStatus, ImportJobType
from app.models.recipe import Recipe
from app.models.user import User
from app.queue import publish_import_job
from app.schemas.import_job import ImportJobCreate, ImportJobRead
from app.settings_service import get_settings

# Any logged-in user can import for themselves (imports are always private to whoever ran them —
# see routers/recipes.py's visibility rule) — gated per-route below, not at the router level.
router = APIRouter(prefix="/imports", tags=["imports"])

_APPROVABLE_STATUSES = {ImportJobStatus.PENDING, ImportJobStatus.FAILED}

_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "instagr.am"}


def _detect_job_type(source: str) -> ImportJobType:
    # Instagram posts need a different fetch path entirely (headless-browser rendering rather
    # than a plain HTML GET — see worker/app/instagram_client.py) since Instagram serves mostly
    # client-side-rendered content. Detected here, once, at creation time so the rest of the
    # pipeline (approval, queueing, the worker's dispatch) just branches on job.type.
    host = (urlparse(source).hostname or "").lower()
    return ImportJobType.INSTAGRAM if host in _INSTAGRAM_HOSTS else ImportJobType.SINGLE


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


def _ensure_category_exists(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise HTTPException(status_code=400, detail="Category does not exist")


def _ensure_source_not_already_imported(db: Session, source: str, owner_id: int) -> None:
    # Scoped to this user, not global — imports are private per owner now, so two different
    # users importing the same public URL each get their own private copy; that's not a
    # duplicate. Exact string match only — not normalized (trailing slash, tracking query
    # params, www. prefix, etc. all count as different URLs). Good enough for "I pasted the same
    # link twice"; revisit if that turns out to be too naive in practice.
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


def _queue_and_publish(db: Session, job: ImportJob) -> None:
    # Commit `queued` *before* publishing, not after: publishing first meant a worker fast
    # enough to consume the message before this transaction committed would read the job's
    # still-stale prior status. Committing first guarantees the queued status is visible to
    # any consumer before the message can possibly reach one.
    job.status = ImportJobStatus.QUEUED
    job.error = None
    db.commit()
    db.refresh(job)

    try:
        publish_import_job(job.id, job.type.value, job.source)
    except Exception as exc:
        job.status = ImportJobStatus.FAILED
        job.error = f"failed to publish to queue: {exc}"
        db.commit()
        db.refresh(job)


@router.get("", response_model=list[ImportJobRead])
def list_import_jobs(
    db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> list[ImportJob]:
    stmt = select(ImportJob).order_by(ImportJob.created_at.desc())
    if not current_user.is_admin:
        stmt = stmt.where(ImportJob.created_by_user_id == current_user.id)
    return list(db.scalars(stmt))


@router.post("", response_model=ImportJobRead, status_code=201)
def create_import_job(
    payload: ImportJobCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> ImportJob:
    user = db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_import_limit_not_reached(db, user)
    _ensure_category_exists(db, payload.category_id)
    _ensure_source_not_already_imported(db, payload.source, current_user.id)

    job = ImportJob(
        source=payload.source,
        category_id=payload.category_id,
        type=_detect_job_type(payload.source),
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

    return job


@router.post("/{job_id}/approve", response_model=ImportJobRead)
def approve_import_job(
    job_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> ImportJob:
    # Also doubles as "retry": a `failed` job (e.g. RabbitMQ was down) can be approved again — by
    # an admin, or by whoever created it.
    job = _get_owned_or_404(db, job_id, current_user)
    if job.status not in _APPROVABLE_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Cannot approve a job in status {job.status.value}"
        )
    _queue_and_publish(db, job)
    return job


@router.get("/{job_id}", response_model=ImportJobRead)
def get_import_job(
    job_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> ImportJob:
    return _get_owned_or_404(db, job_id, current_user)


@router.delete("/{job_id}", status_code=204)
def delete_import_job(
    job_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> None:
    job = _get_owned_or_404(db, job_id, current_user)
    db.delete(job)
    db.commit()
