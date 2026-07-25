from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models.category import Category
from app.models.import_job import ImportJob, ImportJobStatus
from app.models.recipe import Recipe
from app.queue import publish_import_job
from app.schemas.import_job import ImportJobCreate, ImportJobRead

# Every route here is back-office-only — the front office never touches /imports — so the
# whole router is protected at once rather than route by route.
router = APIRouter(prefix="/imports", tags=["imports"], dependencies=[Depends(require_admin)])

_APPROVABLE_STATUSES = {ImportJobStatus.PENDING, ImportJobStatus.FAILED}


def _get_or_404(db: Session, job_id: int) -> ImportJob:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job


def _ensure_category_exists(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise HTTPException(status_code=400, detail="Category does not exist")


def _ensure_source_not_already_imported(db: Session, source: str) -> None:
    # Exact string match only — not normalized (trailing slash, tracking query params, www.
    # prefix, etc. all count as different URLs). Good enough for "I pasted the same link twice";
    # revisit if that turns out to be too naive in practice.
    if db.scalar(select(Recipe).where(Recipe.source_url == source)) is not None:
        raise HTTPException(status_code=409, detail="This URL has already been imported.")
    if db.scalar(select(ImportJob).where(ImportJob.source == source)) is not None:
        raise HTTPException(status_code=409, detail="This URL is already in the import queue.")


@router.get("", response_model=list[ImportJobRead])
def list_import_jobs(db: Session = Depends(get_db)) -> list[ImportJob]:
    return list(db.scalars(select(ImportJob).order_by(ImportJob.created_at.desc())))


@router.post("", response_model=ImportJobRead, status_code=201)
def create_import_job(payload: ImportJobCreate, db: Session = Depends(get_db)) -> ImportJob:
    # Stays `pending` — not published to RabbitMQ — until an admin explicitly approves it.
    _ensure_category_exists(db, payload.category_id)
    _ensure_source_not_already_imported(db, payload.source)

    job = ImportJob(source=payload.source, category_id=payload.category_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/approve", response_model=ImportJobRead)
def approve_import_job(job_id: int, db: Session = Depends(get_db)) -> ImportJob:
    # Also doubles as "retry": a `failed` job (e.g. RabbitMQ was down) can be approved again.
    job = _get_or_404(db, job_id)
    if job.status not in _APPROVABLE_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Cannot approve a job in status {job.status.value}"
        )

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

    return job


@router.get("/{job_id}", response_model=ImportJobRead)
def get_import_job(job_id: int, db: Session = Depends(get_db)) -> ImportJob:
    return _get_or_404(db, job_id)


@router.delete("/{job_id}", status_code=204)
def delete_import_job(job_id: int, db: Session = Depends(get_db)) -> None:
    job = _get_or_404(db, job_id)
    db.delete(job)
    db.commit()
