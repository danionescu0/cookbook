from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import (
    auth,
    categories,
    images,
    imports,
    ingredients,
    languages,
    nutrition,
    public_settings,
    recipes,
    settings as settings_router,
    users,
)

app = FastAPI(title="Cookbook API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(recipes.router)
app.include_router(recipes.me_router)
app.include_router(images.router)
app.include_router(imports.router)
app.include_router(languages.router)
app.include_router(nutrition.router)
app.include_router(ingredients.router)
app.include_router(settings_router.router)
app.include_router(public_settings.router)

Path(settings.images_dir).mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=settings.images_dir), name="images")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
