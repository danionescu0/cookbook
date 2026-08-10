from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.settings_service import get_settings

# Deliberately a separate router from routers/settings.py (which is admin-only at the router
# level) — the signup page needs the Turnstile site key before the visitor has any account, let
# alone a token. The site key itself isn't secret: it's embedded in that page's own HTML.
router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public")
def public_settings(db: Session = Depends(get_db)) -> dict[str, object]:
    row = get_settings(db)
    return {
        "turnstile_site_key": row.turnstile_site_key,
        # Not secret — a plain admin (not just a super-admin) needs this to size the backoffice's
        # recipe pagination, and GET /settings itself is gated to super-admin (it holds secrets).
        "backoffice_recipes_page_size": row.backoffice_recipes_page_size,
        # Not secret either — the Account page needs it to show import usage before the button
        # is disabled, and every visitor (logged in or not) can reach this endpoint.
        "max_imports_per_user": row.max_imports_per_user,
        # Not secret — the login/signup pages need this before the visitor has any account, same
        # reasoning as turnstile_site_key above.
        "google_client_id": row.google_client_id,
    }
