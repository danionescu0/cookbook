from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_super_admin
from app.database import get_db
from app.models.ingredient_refresh_job import IngredientRefreshJob, IngredientRefreshJobStatus
from app.queue import publish_ingredient_refresh_job
from app.schemas.ingredient_refresh import IngredientRefreshJobRead, IngredientRefreshStatusRead

# Lives on the same back office Settings subpage as routers/settings.py, so it's gated to the
# same super-admin tier for consistency — see users.is_super_admin.
router = APIRouter(
    prefix="/ingredients", tags=["ingredients"], dependencies=[Depends(require_super_admin)]
)


def _latest_job(db: Session) -> IngredientRefreshJob | None:
    # id as a tiebreaker: created_at alone isn't precise enough to distinguish two jobs queued
    # within the same second (SQLite's CURRENT_TIMESTAMP has 1s resolution).
    return db.scalar(
        select(IngredientRefreshJob)
        .order_by(IngredientRefreshJob.created_at.desc(), IngredientRefreshJob.id.desc())
        .limit(1)
    )


@router.get("/refresh", response_model=IngredientRefreshStatusRead)
def get_ingredient_refresh_status(db: Session = Depends(get_db)) -> IngredientRefreshStatusRead:
    job = _latest_job(db)
    if job is None:
        return IngredientRefreshStatusRead(status="never_run")
    return IngredientRefreshStatusRead(
        status=job.status.value,
        error=job.error,
        ingredients_updated=job.ingredients_updated,
    )


@router.post("/refresh", response_model=IngredientRefreshJobRead, status_code=201)
def create_ingredient_refresh_job(db: Session = Depends(get_db)) -> IngredientRefreshJob:
    job = IngredientRefreshJob(status=IngredientRefreshJobStatus.QUEUED)
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        publish_ingredient_refresh_job(job.id)
    except Exception as exc:
        job.status = IngredientRefreshJobStatus.FAILED
        job.error = f"failed to publish to queue: {exc}"
        db.commit()
        db.refresh(job)

    return job
