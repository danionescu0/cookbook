from pydantic import BaseModel, ConfigDict


class IngredientRefreshJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # "queued" | "processing" | "done" | "failed"
    status: str
    error: str | None
    ingredients_updated: int | None


class IngredientRefreshStatusRead(BaseModel):
    # "never_run" | "queued" | "processing" | "done" | "failed"
    status: str
    error: str | None = None
    ingredients_updated: int | None = None
