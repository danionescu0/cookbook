from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.recipe import Recipe, RecipeStatus
from app.settings_service import get_settings

# Not nested under any prefix, and specifically routed to at the site root by Caddy (see
# Caddyfile) rather than through the /api/* strip-prefix proxy: the sitemap protocol only allows
# a sitemap to list URLs at or below its own directory, and the URLs here (https://<domain>/en/...)
# are at the site root, not under /api.
router = APIRouter(tags=["sitemap"])

_XML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n'
_URLSET_OPEN = (
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
    'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
)
_URLSET_CLOSE = "</urlset>\n"


def _url_entry(loc: str, alternates: dict[str, str], lastmod: str | None = None) -> str:
    lines = ["  <url>", f"    <loc>{escape(loc)}</loc>"]
    if lastmod:
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
    for lang, href in sorted(alternates.items()):
        lines.append(f'    <xhtml:link rel="alternate" hreflang="{escape(lang)}" href="{escape(href)}"/>')
    lines.append("  </url>")
    return "\n".join(lines)


@router.get("/sitemap.xml")
def sitemap(db: Session = Depends(get_db)) -> Response:
    app_settings = get_settings(db)
    base = app_settings.public_site_url.rstrip("/")
    languages = app_settings.supported_languages_list
    entries: list[str] = []

    # No public_site_url configured yet (a fresh deploy before the admin fills in Settings) means
    # there's no domain to build absolute URLs against — an empty-but-valid sitemap beats a crash.
    if base and languages:
        home_alternates = {lang: f"{base}/{lang}" for lang in languages}
        recipes_alternates = {lang: f"{base}/{lang}/recipes" for lang in languages}
        for lang in languages:
            entries.append(_url_entry(home_alternates[lang], home_alternates))
            entries.append(_url_entry(recipes_alternates[lang], recipes_alternates))

        recipes = db.scalars(
            select(Recipe)
            # Only ever the public set — see routers/recipes.py's visibility rule. A private or
            # pending-approval recipe must never appear here, regardless of who owns it.
            .where(Recipe.status == RecipeStatus.APPROVED, Recipe.is_shared.is_(True))
            .options(selectinload(Recipe.translations))
        )
        for recipe in recipes:
            by_language = {t.language: t for t in recipe.translations if t.language in languages}
            if not by_language:
                continue
            alternates = {
                lang: f"{base}/{lang}/recipes/{recipe.id}-{t.slug}" for lang, t in by_language.items()
            }
            lastmod_dt = recipe.approved_at or recipe.added_at
            lastmod = lastmod_dt.date().isoformat() if lastmod_dt else None
            for loc in alternates.values():
                entries.append(_url_entry(loc, alternates, lastmod))

    body = "\n".join(entries)
    xml = _XML_HEADER + _URLSET_OPEN + (body + "\n" if body else "") + _URLSET_CLOSE
    return Response(content=xml, media_type="application/xml")


# Not a static frontend/public/robots.txt: the sitemap URL needs the actual configured domain
# (public_site_url), and Vite doesn't template files under public/ at build time.
_DISALLOWED_PATHS = (
    "/backoffice",
    "/account",
    "/submit-recipe",
    "/login",
    "/signup",
    "/verify-email",
)


@router.get("/robots.txt")
def robots(db: Session = Depends(get_db)) -> Response:
    app_settings = get_settings(db)
    base = app_settings.public_site_url.rstrip("/")
    lines = ["User-agent: *", *(f"Disallow: {path}" for path in _DISALLOWED_PATHS)]
    if base:
        lines += ["", f"Sitemap: {base}/sitemap.xml"]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")
