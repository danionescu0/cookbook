from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import (
    auth,
    categories,
    contact,
    images,
    imports,
    ingredients,
    languages,
    nutrition,
    public_settings,
    recipes,
    settings as settings_router,
    sitemap,
    users,
)

app = FastAPI(title="Cookbook API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    # Not exposed to frontend JS by default even same-methods/headers-wise — browsers only expose
    # a small response-header safelist across origins unless explicitly listed here. Read by
    # api/client.ts's paginated list calls (recipe list pagination — see routers/recipes.py).
    expose_headers=["X-Total-Count"],
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
app.include_router(sitemap.router)
app.include_router(contact.router)

Path(settings.images_dir).mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=settings.images_dir), name="images")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
