from pydantic import BaseModel


class NutritionTotals(BaseModel):
    calories: float
    protein_g: float
    carbs_g: float
    sugars_g: float
    fat_g: float


class NutritionIngredient(BaseModel):
    index: int
    estimated_grams: float
    grams_source: str


class NutritionRead(BaseModel):
    # "not_enriched" | "queued" | "processing" | "done" | "failed"
    status: str
    error: str | None = None
    estimated_servings: int | None = None
    totals: NutritionTotals | None = None
    per_serving: NutritionTotals | None = None
    per_ingredient: list[NutritionIngredient] = []
