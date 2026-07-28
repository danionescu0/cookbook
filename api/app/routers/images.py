import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.config import settings
from app.database import get_db
from app.image_processing import resize_and_compress
from app.settings_service import get_settings

router = APIRouter(prefix="/images", tags=["images"], dependencies=[Depends(require_admin)])


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
