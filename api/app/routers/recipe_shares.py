import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AuthUser, get_current_user, get_optional_current_user
from app.database import get_db
from app.models.recipe import Recipe, RecipeStatus
from app.models.recipe_ingredient_link import RecipeIngredientLink
from app.models.recipe_share import RecipeShare
from app.models.recipe_translation import RecipeTranslation
from app.routers.images import copy_images
from app.routers.recipes import _get_or_404, _processing_statuses, _resolve_translation, _serialize
from app.schemas.recipe import RecipeRead, RecipeShareDetail, RecipeShareRead, RecipeShareTeaser
from app.settings_service import get_settings
from app.slugify import generate_unique_slug

# Nested under /recipes, for the owner-facing create/list/revoke actions (same prefix
# recipes.py's own favorite/share-with-community endpoints use).
router = APIRouter(prefix="/recipes", tags=["recipe-shares"])
# Top-level, token-addressed — the recipient doesn't know (and shouldn't need) a recipe id, just
# the link they were given.
token_router = APIRouter(prefix="/recipe-shares", tags=["recipe-shares"])

_SHARE_LIFETIME = timedelta(hours=24)
# A real teaser, not a way to read the whole recipe pre-auth — see README Design Decisions
# ("Recipe sharing").
_TEASER_DESCRIPTION_LENGTH = 160


def _ensure_owner_or_admin(recipe: Recipe, current_user: AuthUser) -> None:
    if not current_user.is_admin and recipe.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner or an admin can manage sharing")


def _get_share_or_404(db: Session, token: str) -> RecipeShare:
    share = db.scalar(select(RecipeShare).where(RecipeShare.token == token))
    if share is None:
        raise HTTPException(status_code=404, detail="Share link not found")
    return share


def _share_status(share: RecipeShare) -> str:
    if share.revoked_at is not None:
        return "revoked"
    expires_at = share.expires_at
    # SQLite (test suite) drops tzinfo on round-trip even for a DateTime(timezone=True) column —
    # Postgres doesn't. Same defensive normalization as auth.py's token-expiry checks.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return "expired"
    return "active"


def _share_read(share: RecipeShare) -> RecipeShareRead:
    return RecipeShareRead(
        id=share.id,
        token=share.token,
        created_at=share.created_at,
        expires_at=share.expires_at,
        revoked_at=share.revoked_at,
    )


@router.post("/{recipe_id}/shares", response_model=RecipeShareRead, status_code=201)
def create_share(
    recipe_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> RecipeShareRead:
    recipe = _get_or_404(db, recipe_id)
    _ensure_owner_or_admin(recipe, current_user)

    share = RecipeShare(
        recipe_id=recipe.id,
        token=secrets.token_urlsafe(24),
        created_by_user_id=current_user.id,
        expires_at=datetime.now(timezone.utc) + _SHARE_LIFETIME,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return _share_read(share)


@router.get("/{recipe_id}/shares", response_model=list[RecipeShareRead])
def list_shares(
    recipe_id: int, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> list[RecipeShareRead]:
    recipe = _get_or_404(db, recipe_id)
    _ensure_owner_or_admin(recipe, current_user)

    shares = db.scalars(
        select(RecipeShare).where(RecipeShare.recipe_id == recipe_id).order_by(RecipeShare.created_at.desc())
    )
    return [_share_read(share) for share in shares]


@router.delete("/{recipe_id}/shares/{share_id}", status_code=204)
def revoke_share(
    recipe_id: int,
    share_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
) -> None:
    recipe = _get_or_404(db, recipe_id)
    _ensure_owner_or_admin(recipe, current_user)

    share = db.get(RecipeShare, share_id)
    if share is None or share.recipe_id != recipe_id:
        raise HTTPException(status_code=404, detail="Share link not found")
    # Idempotent: revoking an already-revoked link is a no-op, not an error.
    if share.revoked_at is None:
        share.revoked_at = datetime.now(timezone.utc)
        db.commit()


@token_router.get("/{token}", response_model=RecipeShareDetail)
def get_share(
    token: str,
    db: Session = Depends(get_db),
    current_user: AuthUser | None = Depends(get_optional_current_user),
) -> RecipeShareDetail:
    share = _get_share_or_404(db, token)
    status = _share_status(share)

    if status != "active":
        # Never leak title/image/description past expiry or revocation.
        return RecipeShareDetail(status=status, expires_at=share.expires_at, teaser=None)

    recipe = _get_or_404(db, share.recipe_id)
    default_language = get_settings(db).default_language
    translation = _resolve_translation(recipe, default_language, default_language)

    description = translation.description
    if len(description) > _TEASER_DESCRIPTION_LENGTH:
        description = description[:_TEASER_DESCRIPTION_LENGTH].rstrip() + "…"
    teaser = RecipeShareTeaser(
        title=translation.title,
        image=recipe.images[0] if recipe.images else None,
        description=description,
    )

    if current_user is None:
        return RecipeShareDetail(status=status, expires_at=share.expires_at, teaser=teaser)

    processing_status = _processing_statuses(db, [recipe.id]).get(recipe.id)
    full_recipe = _serialize(recipe, default_language, default_language, processing_status, current_user)
    return RecipeShareDetail(
        status=status,
        expires_at=share.expires_at,
        teaser=teaser,
        shared_by_email=recipe.owner.email,
        recipe=full_recipe,
    )


@token_router.post("/{token}/copy", response_model=RecipeRead, status_code=201)
def copy_share(
    token: str, db: Session = Depends(get_db), current_user: AuthUser = Depends(get_current_user)
) -> RecipeRead:
    share = _get_share_or_404(db, token)
    if _share_status(share) != "active":
        raise HTTPException(status_code=410, detail="This share link has expired")

    original = _get_or_404(db, share.recipe_id)
    default_language = get_settings(db).default_language

    # Private by default, same reasoning create_recipe already documents for a manually-added
    # recipe: nothing to acknowledge/moderate when only the new owner will ever see it. Images are
    # physically duplicated (not the same URLs) — see copy_images's docstring for why.
    copy = Recipe(
        category_id=original.category_id,
        images=copy_images(original.images),
        source_url=original.source_url,
        status=RecipeStatus.APPROVED,
        estimated_servings=original.estimated_servings,
        owner_user_id=current_user.id,
        is_shared=False,
        shared_from_recipe_id=original.id,
    )
    for translation in original.translations:
        copy.translations.append(
            RecipeTranslation(
                language=translation.language,
                title=translation.title,
                description=translation.description,
                ingredients=translation.ingredients,
                steps=translation.steps,
                tips=translation.tips,
                # Freshly generated, not copied — slugs are unique per (language, slug), so the
                # original's can't be reused. Same helper create_recipe/update_recipe use.
                slug=generate_unique_slug(db, translation.language, translation.title),
            )
        )
    db.add(copy)
    db.flush()  # assigns copy.id, needed by the ingredient links below, before the final commit

    original_links = db.scalars(
        select(RecipeIngredientLink).where(RecipeIngredientLink.recipe_id == original.id)
    )
    for link in original_links:
        # Carries over the already-computed nutrition data instantly — the recipient never has to
        # wait for CalorieNinjas/Claude re-enrichment just because ownership changed.
        db.add(
            RecipeIngredientLink(
                recipe_id=copy.id,
                ingredient_index=link.ingredient_index,
                ingredient_id=link.ingredient_id,
                raw_text=link.raw_text,
                estimated_grams=link.estimated_grams,
                grams_source=link.grams_source,
            )
        )

    db.commit()
    db.refresh(copy)
    return _serialize(copy, default_language, default_language, current_user=current_user)
