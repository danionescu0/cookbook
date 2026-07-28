import logging
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.config import settings

logger = logging.getLogger(__name__)

# Below this, the page almost certainly didn't render real post content — most likely a login
# wall or a "post not found" page rather than a genuinely recipe-less caption. Confirmed via a
# live spike (see task #79): a real public post's caption + comments came back well over 1000
# chars; Instagram's own login-wall page text is much shorter than this.
_MIN_BODY_TEXT_LENGTH = 100


class InstagramFetchError(Exception):
    pass


@dataclass
class InstagramPost:
    text: str
    image_url: str | None


def fetch_instagram_post(url: str, timeout_seconds: float) -> InstagramPost:
    """Render an Instagram post/reel headlessly and pull its caption+comments text and preview
    image URL — no login required for public posts (verified live against real posts, both
    interactively and headlessly, before this was built; see the project's task history).

    A fresh browser is launched per call rather than kept warm: these jobs are infrequent and
    admin-approved one at a time (see POST /imports/{id}/approve), not a hot path, so the
    simplicity of not managing persistent browser-process lifecycle wins over startup cost.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=settings.scrape_user_agent,
                    viewport={"width": 1280, "height": 900},
                )
                page = context.new_page()
                page.goto(url, wait_until="load", timeout=int(timeout_seconds * 1000))
                # Instagram's post content streams in after the initial `load` event; a fixed
                # settle delay is what the live spike used successfully. Not tied to a specific
                # DOM element (e.g. `article`) because that selector didn't reliably appear in a
                # headless render even when the content was already present in the page text.
                page.wait_for_timeout(3000)

                if page.locator('input[name="password"]').count() > 0:
                    raise InstagramFetchError(
                        "Instagram asked for a login on this post — it may be private, or "
                        "automated access is temporarily rate-limited."
                    )

                text = page.evaluate("document.body.innerText") or ""
                image_url = page.locator('meta[property="og:image"]').get_attribute("content")
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise InstagramFetchError(f"failed to load Instagram post: {exc}") from exc

    if len(text.strip()) < _MIN_BODY_TEXT_LENGTH:
        raise InstagramFetchError(
            "Couldn't read this Instagram post — it may be private, deleted, or Instagram "
            "blocked automated access."
        )

    return InstagramPost(text=text, image_url=image_url)
