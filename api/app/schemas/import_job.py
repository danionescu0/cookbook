from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.import_job import ImportJobStatus, ImportJobType


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
    error: str | None
    created_at: datetime
    created_by_username: str | None = None
