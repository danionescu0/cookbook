import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.image_processing import resize_and_compress
from app.settings_service import get_settings

# Any logged-in user, not just an admin — non-admins need to attach a photo to a recipe they're
# submitting for review, same as the admin's own manual-create/edit forms.
router = APIRouter(prefix="/images", tags=["images"], dependencies=[Depends(get_current_user)])


@router.post("", status_code=201)
def upload_image(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> dict[str, str]:
    app_settings = get_settings(db)
    content = file.file.read()

    processed = resize_and_compress(
        content, app_settings.image_max_dimension, app_settings.image_max_size_kb
    )
    if processed is None:
        raise HTTPException(status_code=400, detail="That file isn't a valid image")

    images_dir = Path(settings.images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.jpg"
    (images_dir / filename).write_bytes(processed)

    return {"url": f"/images/{filename}"}


def delete_images(image_urls: list[str]) -> None:
    """Best-effort cleanup of files written by upload_image (or the worker's import pipeline,
    same "/images/{uuid}.jpg" naming) — a missing file (already gone, or never existed) is not
    an error, and this must never block whatever DB deletion triggered it.
    """
    images_dir = Path(settings.images_dir)
    for url in image_urls:
        filename = Path(url).name
        (images_dir / filename).unlink(missing_ok=True)
